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
"""Workflow for deploying a Django app to GKE."""

import base64
import os
from typing import Dict
import urllib.parse

import backoff
from django_cloud_deploy.cloudlib import container
import kubernetes
import yaml

from google.auth import credentials


class DeployNewAppError(Exception):
    """Exception raised in deploy new Django app."""
    pass


class DeploygkeWorkflow(object):
    """A class to control the workflow for deploying an Django app to GKE."""

    def __init__(self, credentials: credentials.Credentials):
        self._container_client = container.ContainerClient.from_credentials(
            credentials)
        self._credentials = credentials

    def deploy_new_app_sync(self,
                            project_id: str,
                            cluster_name: str,
                            app_directory: str,
                            app_name: str,
                            image_name: str,
                            secrets: Dict[str, Dict[str, str]],
                            region: str = 'us-west1',
                            zone: str = 'us-west1-a') -> str:
        """Deploy a Django app to gke.

        Args:
            project_id: GCP project id.
            cluster_name: Name of the cluster to host the app.
            app_directory: Absolute path of the directory of your Django app.
            app_name: Name of the Django app.
            image_name: Tag of the docker image of the app.
            secrets: Secrets necessary to run the app.
            region: Where do you want to host the cluster.
            zone: Name of the Google Compute Engine zone in which the cluster
                resides.

        Raises:
            DeployNewAppError: If unable to deploy the app.

        Returns:
            The url of the deployed Django app.
        """

        self._container_client.create_cluster_sync(project_id, cluster_name,
                                                   region, zone)
        self._container_client.build_docker_image(image_name, app_directory)
        self._container_client.push_docker_image(image_name)
        yaml_file_path = os.path.join(app_directory, app_name + '.yaml')
        with open(yaml_file_path) as yaml_file:
            for data in yaml.load_all(yaml_file, Loader=yaml.FullLoader):
                if data['kind'] == 'Deployment':
                    deployment_data = data
                elif data['kind'] == 'Service':
                    service_data = data

        # This happens if the generated Django app does not have a valid yaml
        # file.
        if not deployment_data or not service_data:
            raise DeployNewAppError(
                ('Invalid kubernetes configuration file for Django app '
                 '"{}" in "{}"').format(app_name, app_directory))
        kube_config = self._container_client.create_kubernetes_configuration(
            self._credentials, project_id, cluster_name, zone)
        for secret_name, secret in secrets.items():
            for key, value in secret.items():
                if isinstance(value, str):
                    value = value.encode('utf-8')

                # Kubernetes api only accepts base64 encoded strings.
                # See https://github.com/kubernetes-client/python/blob/master/kubernetes/docs/V1Secret.md  # noqa: E501
                secret[key] = base64.standard_b64encode(value).decode('utf-8')
            secret_data = kubernetes.client.V1Secret(
                api_version='v1',
                data=secret,
                kind='Secret',
                metadata={'name': secret_name})
            self._container_client.create_secret(secret_data, kube_config)
        self._container_client.create_deployment(deployment_data, kube_config)
        self._wait_for_deployment_ready(kube_config, app_name)
        self._container_client.create_service(service_data, kube_config)
        ingress_url = self._get_ingress_url(kube_config)
        return ingress_url

    def update_app_sync(self,
                        project_id: str,
                        cluster_name: str,
                        app_directory: str,
                        app_name: str,
                        image_name: str,
                        zone: str = 'us-west1-a') -> str:
        """Update an existing Django app on gke.

        Args:
            project_id: GCP project id.
            cluster_name: Name of the cluster to host the app.
            app_directory: Absolute path of the directory of your Django app.
            app_name: Name of the Django app.
            image_name: Tag of the docker image of the app.
            zone: Name of the Google Compute Engine zone in which the cluster
                resides.

        Raises:
            DeployNewAppError: If unable to deploy the app.

        Returns:
            The url of the deployed Django app.
        """
        self._container_client.build_docker_image(image_name, app_directory)
        self._container_client.push_docker_image(image_name)
        yaml_file_path = os.path.join(app_directory, app_name + '.yaml')
        with open(yaml_file_path) as yaml_file:
            for data in yaml.load_all(yaml_file, Loader=yaml.FullLoader):
                if data['kind'] == 'Deployment':
                    deployment_data = data

        # This happens if the generated Django app does not have a valid yaml
        # file.
        if not deployment_data:
            raise DeployNewAppError(
                ('Invalid kubernetes configuration file for Django app '
                 '"{}" in "{}"').format(app_name, app_directory))
        kube_config = self._container_client.create_kubernetes_configuration(
            self._credentials, project_id, cluster_name, zone)
        self._container_client.update_deployment(deployment_data, kube_config)
        self._wait_for_deployment_ready(kube_config, app_name)
        ingress_url = self._get_ingress_url(kube_config)
        return ingress_url

    def _get_ingress_url(self,
                         kube_config: kubernetes.client.Configuration) -> str:
        """Returns the URL that can be used to access the app.

        Args:
            kube_config: A kubernetes configuration which has access to the
                given cluster.

        Returns:
            Url of the deployed Django app.
        """

        api_client = kubernetes.client.ApiClient(kube_config)
        api = kubernetes.client.CoreV1Api(api_client)
        return self._try_get_ingress_url(api)

    @backoff.on_predicate(backoff.constant, interval=0.5, logger=None)
    def _try_get_ingress_url(self, api: kubernetes.client.CoreV1Api) -> str:
        """Return Ingress url when service is ready."""
        items = api.list_service_for_all_namespaces().items
        for item in items:
            ingress = item.status.load_balancer.ingress
            if ingress:
                return 'http://{}/'.format(ingress[0].hostname or ingress[0].ip)

        # @backoff.on_predicate(backoff.constant) will keep running this method
        # until it gets a non-falsey result. Return value of '' means that the
        # service is not ready yet.
        return ''

    def _wait_for_deployment_ready(self,
                                   kube_config: kubernetes.client.Configuration,
                                   app_name: str):
        """Wait for the deployment of Django app to get ready.

        Args:
            kube_config: A kubernetes configuration which has access to the
                given cluster.
            app_name: Name of the Django app.
        """

        api_client = kubernetes.client.ApiClient(kube_config)
        api = kubernetes.client.ExtensionsV1beta1Api(api_client)
        label_selector = '='.join(['app', app_name])
        self._try_get_ready_replicas(api, label_selector)

    @backoff.on_predicate(backoff.constant, interval=0.5, logger=None)
    def _try_get_ready_replicas(self,
                                api: kubernetes.client.ExtensionsV1beta1Api,
                                label_selector: str) -> int:
        """Return ready replicas when deployment is ready."""
        items = api.list_deployment_for_all_namespaces(
            label_selector=label_selector).items
        for item in items:
            if item.status.ready_replicas:
                return item.status.ready_replicas

        # @backoff.on_predicate(backoff.constant) will keep running this method
        # until it gets a non-falsey result. Return value of 0 means that the
        # deployment is not ready yet.
        return 0
