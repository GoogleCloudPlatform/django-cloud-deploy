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

import json
import os
import subprocess
import time
import urllib.parse
import webbrowser

import docker
import jinja2
import kubernetes

import google.api_core.exceptions
from google.cloud import container_v1
from google.cloud import storage

from django_cloud_deploy.utils import base_client


class DeploygkeWorkflow(base_client.BaseClient):
    """The class to help deployment of a django app to gke.

  This class will do the following for the Django app:
    1. Build and push docker images.
    2. Create a Kubernetes cluster if it does not exist on cloud.
    3. Deploy the Django app with the generated yaml file
    4. Create a GCS bucket to hold your app's static content
    5. Collect static content from your app and upload it to the bucket just
       created.
  """

    def __init__(self,
                 project_id,
                 project_name,
                 project_path,
                 storage_client=None,
                 debug=False):
        """Deploy a Django app to GKE.

    Args:
      project_id: str, Google Cloud Platform project id.
      project_name: str, Django project name.
      project_path: str, path to the folder containing your Django project.
      storage_client: None or google.cloud.storage.Client. This parameter is
                      test only.
      debug: bool. Whether to suppress subprocess output.
    """
        super().__init__(debug)
        self._project_id = project_id
        self._project_name = project_name
        self._project_path = project_path
        self._project_image_tag = '/'.join(['gcr.io', project_id, project_name])
        self._docker_client = docker.from_env()
        self._storage_client = storage_client or storage.Client(project_id)

    def _get_template_folder_path(self):
        dirname, _ = os.path.split(os.path.abspath(__file__))
        return os.path.join(dirname, 'templates')

    def _collect_static_content(self):
        cwd = os.getcwd()
        os.chdir(self._project_path)
        settings_module = '.'.join([self._project_name, 'remote_settings'])
        subprocess.check_call([
            'django-admin', 'collectstatic',
            '='.join(['--pythonpath', self._project_path]), '='.join(
                ['--settings', settings_module])
        ])
        os.chdir(cwd)

    def _create_gcs_bucket(self, bucket_name=None):
        """Create Google Cloud Storage bucket and make it public."""
        bucket_name = bucket_name or self._project_id
        print('Creating Google Cloud Storage bucket {}'.format(bucket_name))
        bucket = self._storage_client.create_bucket(bucket_name)
        bucket.make_public(recursive=True, future=True)
        return bucket

    def _upload_static_content(self, bucket):
        """Upload collected static content to GCS bucket."""
        files_uploaded = []
        print('Uploading static files to Google Cloud Storage. This might take '
              'several minutes.')
        self._upload_static_content_recursive(bucket, 'static', files_uploaded)
        return files_uploaded

    def _upload_static_content_recursive(self, bucket, current_path,
                                         files_uploaded):
        """A helper function to upload files to gcs buckets.

    Python Cloud Storage Client does not support uploading folders. So we need
    a function to upload all files under a folder.

    Args:
      bucket: google.cloud.storage.bucket.Bucket, your GCS bucket to hold
              static contents.
      current_path: str, the current folder path. This is the relative path
                    with the root of static content folder.
      files_uploaded: List[str], the list of paths of files uploaded.
    """

        # current_folder_path is an absolute path
        current_folder_path = os.path.join(self._project_path, current_path)

        for file_or_folder in os.listdir(current_folder_path):

            # file_or_folder_path is an absolute path
            file_or_folder_path = os.path.join(current_folder_path,
                                               file_or_folder)
            if os.path.isdir(file_or_folder_path):

                # current_path and file_or_folder are both relative path with
                # the current folder.
                relative_folder_path = os.path.join(current_path,
                                                    file_or_folder)
                self._upload_static_content_recursive(
                    bucket, relative_folder_path, files_uploaded)
            else:
                gcs_file_path = os.path.join(current_path, file_or_folder)
                blob = bucket.blob(gcs_file_path)
                blob.upload_from_filename(file_or_folder_path)
                files_uploaded.append(gcs_file_path)

    @staticmethod
    def _get_ingress_url():
        """Returns the URL that can be used to access the app."""
        kubernetes.config.load_kube_config()
        api = kubernetes.client.CoreV1Api()
        # TODO: Replace the adhoc progress indication with something
        # more systematic.
        print('Waiting for application to start.', sep='', end='', flush=True)
        while True:
            items = api.list_service_for_all_namespaces().items
            for item in items:
                ingress = item.status.load_balancer.ingress
                if ingress:
                    print()  # Move to the next line.
                    return 'http://{}/'.format(ingress[0].hostname or
                                               ingress[0].ip)
            print('.', sep='', end='', flush=True)
            time.sleep(0.5)

    def _wait_for_deployment_ready(self):
        """Wait for the deployment of Django app to get ready."""
        kubernetes.config.load_kube_config()
        api = kubernetes.client.ExtensionsV1beta1Api()
        label_selector = '='.join(['app', self._project_name])
        print(
            'Waiting for deployment to get ready.', sep='', end='', flush=True)
        # TODO: Add error handling. What we should do if the deployment is
        # never ready.
        while True:
            items = api.list_deployment_for_all_namespaces(
                label_selector=label_selector).items
            for item in items:
                if item.status.ready_replicas:
                    print()  # Move to the next line.
                    # Return value is only used in test.
                    return item.status.ready_replicas
                print('.', sep='', end='', flush=True)
            time.sleep(0.5)

    def deploygke(self,
                  service_account_key_path,
                  admin_user_name,
                  cluster_name=None,
                  bucket_name=None,
                  image_tag=None,
                  open_browser=True):
        """Go through all steps to deploy an app to gke.

    Args:
      service_account_key_path: str, the absolute path of your service account
                                key.
      admin_user_name: str, the user name of your superuser account.
      cluster_name: str or None, name of the cluster to deploy the Django app.
        This is only used in test.
      bucket_name: str or None, name of the bucket to upload the static
        contents. This is only used in test.
      image_tag: str or None, tag of the docker image of the Django app.
        This is only used in test.
      open_browser: bool, whether to open the web browser showing the deployed
        Django app at the end.
    Returns:
      url of admin site of the deployed Django app.
    """
        cluster_name = cluster_name or self._project_name
        bucket_name = bucket_name or self._project_id
        image_tag = image_tag or self._project_image_tag
        self._create_cluster(cluster_name=cluster_name)
        self._configure_kubectl(cluster_name=cluster_name)
        self._create_cloudsql_secrets(service_account_key_path)
        self._build_docker_image(image_tag)
        self._push_docker_image(image_tag)
        self._serve_static_content_workflow(bucket_name)
        self._create_service_and_deployment()
        self._wait_for_deployment_ready()

        ingress_url = self._get_ingress_url()
        admin_url = urllib.parse.urljoin(ingress_url, '/admin')
        print('Your application is running at: {0}'.format(admin_url))
        print('You can login to the admin page with username "{0}" and your '
              'database password.'.format(admin_user_name))
        if open_browser:
            input('Press enter to open your site.')
            webbrowser.open(admin_url)
        return admin_url

    def updategke(self):
        """Go through all steps to update an deployed app."""
        self._build_docker_image()
        self._push_docker_image()
        self._update_service_and_deployment()
        self._wait_for_deployment_ready()

        ingress_url = self._get_ingress_url()
        admin_url = urllib.parse.urljoin(ingress_url, '/admin')
        print('Your application is running at: {0}'.format(admin_url))
        input('Press enter to open your site.')
        webbrowser.open(admin_url)

    def _serve_static_content_workflow(self, bucket_name):
        self._collect_static_content()
        bucket = self._create_gcs_bucket(bucket_name)
        self._upload_static_content(bucket)

    def _build_docker_image(self, tag=None):
        tag = tag or self._project_image_tag
        print('Building docker image', tag)
        self._docker_client.images.build(tag=tag, path=self._project_path)

    def _push_docker_image(self, tag=None):
        tag = tag or self._project_image_tag
        print('Pushing docker image to', tag)
        self._docker_client.images.push(tag)

    def _get_default_kubernetes_version(self, zone='us-west1-a'):
        query_default_version_args = [
            'gcloud', 'container', 'get-server-config', '--zone', zone,
            '--format=csv[no-heading](defaultClusterVersion)'
        ]
        output = subprocess.check_output(
            query_default_version_args,
            universal_newlines=True,
            stderr=self._stderr)
        return output.strip()

    def _create_cluster(self,
                        cluster_name,
                        region='us-west1',
                        zone='us-west1-a'):
        """Create a cluster with your GCP account.

    Args:
      cluster_name: str, name of your cluster.`
      region: str, where do you want to host the cluster.
      zone: str, the name of the Google Compute Engine zone in which the
            cluster resides.

    Available region and zones can be found on
    https://cloud.google.com/compute/docs/regions-zones/#available
    """

        search_path = self._get_template_folder_path()
        template_loader = jinja2.FileSystemLoader(searchpath=search_path)
        template_env = jinja2.Environment(loader=template_loader)
        template = template_env.get_template('cluster_definition.json')

        kubernetes_version = self._get_default_kubernetes_version(zone)
        content = template.render({
            'cluster_name': cluster_name,
            'project_id': self._project_id,
            'region': region,
            'kubernetes_version': kubernetes_version,
        })
        cluster_data = json.loads(content)
        client = container_v1.ClusterManagerClient()
        try:
            print('Create Kubernetes cluster', cluster_name)
            client.create_cluster(
                project_id=self._project_id,
                zone=zone,
                cluster=cluster_data['cluster'])
            print('Waiting for cluster to get ready. This should take less '
                  'than 5 minutes')
            time_to_wait = 300
            while time_to_wait > 0:
                response = client.get_cluster(self._project_id, zone,
                                              cluster_name)
                if response.status == 2:  # means cluster is ready
                    break
                else:
                    time_to_wait -= 5
                    time.sleep(5)
            if time_to_wait <= 0:
                print('Cluster not ready after 5 minutes.')
        except google.api_core.exceptions.AlreadyExists:
            print('Cluster {} already exists. We will reuse that cluster.'.
                  format(cluster_name))

    def _create_service_and_deployment(self):
        """Create Kubernetes deployment and service from yaml file."""
        yaml_file_path = os.path.join(self._project_path,
                                      self._project_name + '.yaml')
        subprocess.check_call(['kubectl', 'apply', '-f', yaml_file_path],
                              stdout=self._stdout,
                              stderr=self._stderr)
        print(
            'Successfully created service. It should be ready within a minute.')

    def _update_service_and_deployment(self):
        deployment_name = '/'.join(['deployment', self._project_name])
        set_image_str = '{}-app={}:latest'.format(self._project_name,
                                                  self._project_image_tag)
        subprocess.check_call(
            ['kubectl', 'set', 'image', deployment_name, set_image_str],
            stdout=self._stdout,
            stderr=self._stderr)
        print(
            'Successfully updated service. It should be ready within a minute.')

    def _configure_kubectl(self, cluster_name, zone='us-west1-a'):
        """Configure kubectl to make it point to the newly created cluster.

    Args:
      cluster_name: str, name of the newly created cluster.
      zone: str, zone of the cluster.
    """
        subprocess.check_call([
            'gcloud', 'container', 'clusters', 'get-credentials', cluster_name,
            '--zone', zone
        ],
                              stdout=self._stdout,
                              stderr=self._stderr)
        kubernetes.config.load_kube_config()

    def _create_cloudsql_secrets(self, service_account_key_path):
        """Save all sensitive information with Kubernetes secrets.

    Args:
      service_account_key_path: str, the path of service account key.
    """
        print('Create cloudsql secrets')

        username = os.environ['DATABASE_USER']
        password = os.environ['DATABASE_PASSWORD']
        subprocess.check_call([
            'kubectl', 'create', 'secret', 'generic',
            'cloudsql-oauth-credentials',
            ('--from-file=credentials.json=' + service_account_key_path)
        ],
                              stdout=self._stdout,
                              stderr=self._stderr)
        subprocess.check_call([
            'kubectl', 'create', 'secret', 'generic', 'cloudsql',
            '--from-literal=username=' + username,
            '--from-literal=password=' + password
        ],
                              stdout=self._stdout,
                              stderr=self._stderr)
