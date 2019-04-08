# Copyright 2018 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Manages Resources related to Google Kubernetes Engine.

For example, docker image build and push, cluster creation, deployment and
service exposing.
"""

import atexit
import base64
import json
import os
import tempfile
import time

import docker
from googleapiclient import discovery
from googleapiclient import errors
import jinja2
import kubernetes

from google.auth import credentials
from google.auth.transport import requests

_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), 'data')
_CLUSTER_TEMPLATE_NAME = 'cluster_definition.json'


class ContainerCreationError(Exception):
    """Exception raised in container creation."""
    pass


class ClusterGetInfoError(Exception):
    """Exception raised in trying to get information of a cluster."""
    pass


class ContainerClient(object):
    """The class for deployment of a Django app to gke.

    We should call the methods of this class in the following order:
        1. Call create_cluster_sync to create a new cluster.
        2. Call build_docker_image.
        3. Call push_docker_image.
        4. Call create_kubernetes_configuration to get a configuration object
           to access the newly created cluster.
        5. Call create_secret to create secret objects to hold sensitive
           information necessary for the deployment of your Django app. These
           information can be accessed inside pods of your Django app.
        6. Call create_deployment.
        7. Call create_service.
    """

    # This class will create temporary files for cluster ca certificates.
    # This variable is used to save the path of those temporary files and
    # remove them after the program exists.
    _temp_ca_files = []

    def __init__(self, container_service: discovery.Resource,
                 credentials: credentials.Credentials):
        self._container_service = container_service
        self._create_docker_client(credentials)

    def _create_docker_client(self, credentials: credentials.Credentials):
        # credentials.token is a bearer token that can be used in HTTP headers
        # to make authenticated requests. When the given credentials does not
        # have token, we need to force it to get a new token.
        if not credentials.token:
            credentials.refresh(requests.Request())

        # See https://cloud.google.com/container-registry/docs/advanced-authentication
        self._docker_client = docker.DockerClient()
        self._docker_client.login(username='oauth2accesstoken',
                                  password=credentials.token,
                                  registry='https://gcr.io')

    @classmethod
    def from_credentials(cls, credentials: credentials.Credentials):
        return cls(
            discovery.build('container',
                            'v1',
                            credentials=credentials,
                            cache_discovery=False), credentials)

    @staticmethod
    def _load_cluster_definition_template():
        template_loader = jinja2.FileSystemLoader(searchpath=_TEMPLATE_DIR)
        template_env = jinja2.Environment(loader=template_loader)
        template = template_env.get_template(_CLUSTER_TEMPLATE_NAME)
        return template

    def _cleanup_temp_files(self):
        for temp_ca_file in self._temp_ca_files:
            try:
                os.remove(temp_ca_file)
            except OSError:
                pass
        self._temp_ca_files = []

    def _get_default_kubernetes_version(self, project_id, zone='us-west1-a'):
        name = 'projects/{}/locations/{}'.format(project_id, zone)
        request = self._container_service.projects().locations(
        ).getServerConfig(name=name)
        response = request.execute(num_retries=5)
        if 'defaultClusterVersion' not in response:
            raise ContainerCreationError('')
        return response['defaultClusterVersion']

    def create_cluster_sync(self,
                            project_id: str,
                            cluster_name: str,
                            region: str = 'us-west1',
                            zone: str = 'us-west1-a'):
        """Create a cluster with your GCP account.

        Available region and zones can be found on
        https://cloud.google.com/compute/docs/regions-zones/#available

        Args:
            project_id: The id of your GCP project to create cluster in.
            cluster_name: The name of your cluster to create.
            region: Where do you want to host the cluster.
            zone: Name of the Google Compute Engine zone in which the cluster
                resides.

        Raises:
            ContainerCreationError: If unable to create a cluster.
        """

        template = ContainerClient._load_cluster_definition_template()
        kubernetes_version = self._get_default_kubernetes_version(
            project_id, zone)
        cluster_definition = template.render({
            'cluster_name':
            cluster_name,
            'project_id':
            project_id,
            'region':
            region,
            'kubernetes_version':
            kubernetes_version,
        })
        body = json.loads(cluster_definition)
        request = self._container_service.projects().zones().clusters().create(
            projectId=project_id, zone=zone, body=body)
        try:
            request.execute(num_retries=5)
        except errors.HttpError as e:
            if e.resp.status == 403:
                raise ContainerCreationError(
                    ('You do not have permission to create a cluster in '
                     'project: "{}"').format(project_id))
            elif e.resp.status == 409:
                # Cluster with the same name already exist. It is fine to reuse
                # the same cluster for deployment.
                pass
            else:
                raise ContainerCreationError(
                    ('Unexpected error when creating cluster "{}" in '
                     'project "{}"').format(cluster_name, project_id)) from e

        while True:
            request = self._container_service.projects().zones().clusters().get(
                projectId=project_id, zone=zone, clusterId=cluster_name)
            response = request.execute(num_retries=5)

            # Possible status:
            # https://cloud.google.com/kubernetes-engine/docs/reference/rest/v1/projects.zones.clusters#Status
            if response['status'] == 'RUNNING':
                return
            elif response['status'] == 'PROVISIONING':
                time.sleep(2)
                continue
            else:
                raise ContainerCreationError(
                    'Unexpected cluster status after creation: {!r}'.format(
                        response['status']))

    def create_kubernetes_configuration(self,
                                        credentials: credentials.Credentials,
                                        project_id: str,
                                        cluster_name: str,
                                        zone: str = 'us-west1-a'
                                       ) -> kubernetes.client.Configuration:
        """Create a kubernetes config which has access to the given cluster.

        Args:
            credentials: The credentials object used to generate tokens to
                access kubernetes clusters.
            project_id: GCP project id.
            cluster_name: Name of the kubernetes cluster we want to access.
            zone: Where is the cluster hosted.

        Raises:
            ClusterGetInfoError: When unexpected cluster information is returned
                from GCP.

        Returns:
            A kubernetes configuration which has access to the provided cluster.
        """

        # This function will create a temporary file for cluster ca certificate.
        # Those temporary files should be removed after the program exists.
        if not ContainerClient._temp_ca_files:
            atexit.register(self._cleanup_temp_files)

        # credentials.token is a bearer token that can be used in HTTP headers
        # to make authenticated requests. When the given credentials does not
        # have token, we need to force it to get a new token.
        if not credentials.token:
            credentials.refresh(requests.Request())

        request = self._container_service.projects().zones().clusters().get(
            projectId=project_id, zone=zone, clusterId=cluster_name)
        response = request.execute(num_retries=5)
        if ('masterAuth' not in response or
                'clusterCaCertificate' not in response['masterAuth']):
            raise ClusterGetInfoError(
                ('Unexpected response getting information of cluster "{}" in '
                 'project "{}": {}').format(cluster_name, project_id, response))

        ca = response['masterAuth']['clusterCaCertificate']

        _, ca_file_path = tempfile.mkstemp()
        # Save temporary file path so that it can be cleaned up after the
        # program exits.
        self._temp_ca_files.append(ca_file_path)
        with open(ca_file_path, 'wb') as ca_file:
            ca_file.write(base64.standard_b64decode(ca))
        configuration = kubernetes.client.Configuration()
        configuration.api_key['authorization'] = credentials.token
        configuration.api_key_prefix['authorization'] = 'Bearer'
        configuration.host = 'https://' + response['endpoint']
        configuration.ssl_ca_cert = ca_file_path
        return configuration

    def build_docker_image(self, tag: str, directory: str):
        """Build docker image.

        Args:
            tag: Docker image tag. Should looks similar to
                "gcr.io/<project_id>/<image_name>"
            directory: Absolute path of the directory containing a Dockerfile.
        """

        self._docker_client.images.build(tag=tag, path=directory)

    def push_docker_image(self, tag: str):
        """Push docker image.

        Args:
            tag: Docker image tag. Should looks similar to
                "gcr.io/<project_id>/<image_name>"
        """
        self._docker_client.images.push(tag)

    def create_deployment(
            self,
            deployment_data: kubernetes.client.V1Deployment,
            configuration: (
                kubernetes.client.configuration.Configuration) = None,
            namespace: str = 'default'):
        """Create a Kubernetes Deployment.

        A Kubernetes Deployment describes a desired state of your application.
        For example, it manages creation of Pods by means of ReplicaSets, and
        defines what images to use for the containers.

        Args:
            deployment_data: Definition of the deployment.
            configuration: A Kubernetes configuration which has access to the
                cluster for the deployment. If not set, it will use the default
                kubernetes configuration.
            namespace: Namespace of the deployment.
        """
        api_client = kubernetes.client.ApiClient(configuration)
        api_instance = kubernetes.client.ExtensionsV1beta1Api(api_client)
        api_instance.create_namespaced_deployment(namespace=namespace,
                                                  body=deployment_data)

    def update_deployment(
            self,
            deployment_data: kubernetes.client.V1Deployment,
            configuration: (
                kubernetes.client.configuration.Configuration) = None,
            namespace: str = 'default'):
        """Update a Kubernetes Deployment.

        A Kubernetes Deployment describes a desired state of your application.
        For example, it manages creation of Pods by means of ReplicaSets, and
        defines what images to use for the containers.

        Args:
            deployment_data: Definition of the deployment.
            configuration: A Kubernetes configuration which has access to the
                cluster for the deployment. If not set, it will use the default
                kubernetes configuration.
            namespace: Namespace of the deployment.
        """

        api_client = kubernetes.client.ApiClient(configuration)
        api_instance = kubernetes.client.ExtensionsV1beta1Api(api_client)

        deployment_name = deployment_data['metadata']['name']

        # TODO: Find a better way to do update.
        # Right now we scale the replicas to 0 and then scale it back. This
        # will trigger an image update.
        replicas = deployment_data['spec']['replicas']
        deployment_data['spec']['replicas'] = 0
        api_instance.patch_namespaced_deployment(name=deployment_name,
                                                 namespace=namespace,
                                                 body=deployment_data)
        deployment_data['spec']['replicas'] = replicas
        api_instance.patch_namespaced_deployment(name=deployment_name,
                                                 namespace=namespace,
                                                 body=deployment_data)

    def create_service(
            self,
            service_data: kubernetes.client.V1Service,
            configuration: (
                kubernetes.client.configuration.Configuration) = None,
            namespace: str = 'default'):
        """Create a Kubernetes Dervice.

        A Kubernetes Service is an abstraction which defines a logical set of
        Pods and a policy by which to access them.

        Args:
            service_data: Definition of the service.
            configuration: A Kubernetes configuration which has access to the
                cluster for the service. If not set, it will use the default
                kubernetes configuration.
            namespace: Namespace of the service.
        """
        api_client = kubernetes.client.ApiClient(configuration)
        api_instance = kubernetes.client.CoreV1Api(api_client)
        api_instance.create_namespaced_service(namespace=namespace,
                                               body=service_data)

    def create_secret(self,
                      secret_data: kubernetes.client.V1Secret,
                      configuration: (
                          kubernetes.client.configuration.Configuration) = None,
                      namespace: str = 'default'):
        """Create a Kubernetes Secret.

        Kubernetes Secrets are intended to hold sensitive information. They are
        accessible inside Pods.

        Args:
            secret_data: Definition of the secret.
            configuration: A Kubernetes configuration which has access to the
                cluster for the service. If not set, it will use the default
                kubernetes configuration.
            namespace: Namespace of the service.
        """
        api_client = kubernetes.client.ApiClient(configuration)
        api_instance = kubernetes.client.CoreV1Api(api_client)
        api_instance.create_namespaced_secret(namespace=namespace,
                                              body=secret_data)
