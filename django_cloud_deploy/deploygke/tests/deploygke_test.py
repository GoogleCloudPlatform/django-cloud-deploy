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
import shutil
import tempfile
from unittest import mock

from absl.testing import absltest
import kubernetes
import responses

import google.auth.credentials
from google.cloud import storage

from django_cloud_deploy.deploygke import deploygke

DEPLOYMENT_YAML_TEMPLATE = """
apiVersion: extensions/v1beta1
kind: Deployment
spec:
  template:
    spec:
      containers:
      - image: gcr.io/%s/%s
"""

SERVICE_YAML_TEMPLATE = """
apiVersion: v1
kind: Service
spec:
  type: LoadBalancer
  ports:
  - port: 80
    targetPort: 8080
  selector:
    app: %s
"""

SETTINGS_FILE_CONTENT = """
SECRET_KEY = '123'

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'polls',
)

STATIC_URL = '/static/'
STATIC_ROOT = 'static/'
"""


class MockGetClusterResponse(object):

    def __init__(self, status=2):
        self.status = status


def _make_credentials():
    return mock.Mock(spec=google.auth.credentials.Credentials)


class DeploygkeWorkflowTest(absltest.TestCase):

    STATIC_FILE_CONTENT = 'This is a static file.'

    def setUp(self):
        # Create a temporary directory to put Django project files
        self._project_dir = tempfile.mkdtemp()
        self._project_id = 'deploygke_test_id'
        self._project_name = 'deploygke_test_name'
        self._patcher = mock.patch('kubernetes.config.load_kube_config')
        self._patcher.start()
        self._bucket_name = self._project_id
        storage_client = storage.Client(
            self._project_id, credentials=_make_credentials())
        self._deploygke_workflow = deploygke.DeploygkeWorkflow(
            self._project_id,
            self._project_name,
            self._project_dir,
            storage_client=storage_client)
        self._generate_yaml()

    def tearDown(self):
        # Remove the directory after the test
        shutil.rmtree(self._project_dir)
        self._patcher.stop()

    def _generate_yaml(self):
        deployment_yaml = DEPLOYMENT_YAML_TEMPLATE % (self._project_id,
                                                      self._project_name)
        service_yaml = SERVICE_YAML_TEMPLATE % self._project_name
        kubernete_yaml = ''.join([deployment_yaml, '\n---\n', service_yaml])
        yaml_file_path = os.path.join(self._project_dir,
                                      self._project_name + '.yaml')
        with open(yaml_file_path, 'w') as yaml_file:
            yaml_file.write(kubernete_yaml)

    @mock.patch('docker.models.images.ImageCollection.build', autoSpec=True)
    def test_build_docker_image(self, mock_image_build):
        self._deploygke_workflow._build_docker_image()
        mock_image_build.assert_called_with(
            path=self._project_dir,
            tag=self._deploygke_workflow._project_image_tag)

    @mock.patch('docker.models.images.ImageCollection.push', autoSpec=True)
    def test_push_docker_image(self, mock_image_push):
        self._deploygke_workflow._push_docker_image()
        mock_image_push.assert_called_with(
            self._deploygke_workflow._project_image_tag)

    @mock.patch(
        'google.cloud.container_v1.ClusterManagerClient.create_cluster',
        autoSpec=True)
    @mock.patch(
        'google.cloud.container_v1.ClusterManagerClient.get_cluster',
        autoSpec=True,
        return_value=MockGetClusterResponse())
    @mock.patch(('django_cloud_deploy.deploygke.deploygke.DeploygkeWorkflow.'
                 '_get_default_kubernetes_version'),
                autoSpec=True)
    def test_create_cluster(self, mock_get_version, unused_mock_get_cluster,
                            mock_create_cluster):
        fake_kubernetes_version = 'fake_kubernetes_version'
        mock_get_version.return_value = fake_kubernetes_version
        cluster_name = 'deploygke_test_cluster'
        self._deploygke_workflow._create_cluster(cluster_name)

        _, kwargs = mock_create_cluster.call_args
        cluster_definition = kwargs['cluster']
        self.assertEqual(cluster_definition['name'], cluster_name)
        self.assertIn(self._project_id, cluster_definition['network'])
        self.assertIn('us-west', cluster_definition['subnetwork'])
        self.assertEqual(fake_kubernetes_version,
                         cluster_definition['initial_cluster_version'])
        self.assertEqual(fake_kubernetes_version,
                         cluster_definition['node_pools'][0]['version'])

    def _setup_django_files(self):
        # Create project folder
        project_folder_path = os.path.join(self._project_dir,
                                           self._project_name)
        os.mkdir(project_folder_path)

        settings_path = os.path.join(self._project_dir, self._project_name,
                                     'remote_settings.py')
        # This is used to find and collect static files for installed Django
        # apps.
        os.environ.setdefault('DJANGO_SETTINGS_MODULE',
                              '.'.join([self._project_name, 'remote_settings']))
        with open(settings_path, 'w') as settings_file:
            settings_file.write(SETTINGS_FILE_CONTENT)

        app_name = 'polls'

        # Create folder holding static files in apps
        app_static_folder = os.path.join(self._project_dir, app_name, 'static',
                                         'polls')
        # exist_ok=True enables creating parent folders.
        os.makedirs(app_static_folder, exist_ok=True)
        app_static_file_path = os.path.join(app_static_folder, 'style.css')
        with open(app_static_file_path, 'w') as css_file:
            css_file.write(self.STATIC_FILE_CONTENT)

    def test_collect_static_files(self):
        self._setup_django_files()
        self._deploygke_workflow._collect_static_content()
        files_list = os.listdir(os.path.join(self._project_dir, 'static'))
        self.assertCountEqual(('polls',), files_list)

        files_list = os.listdir(
            os.path.join(self._project_dir, 'static', 'polls'))
        self.assertCountEqual(('style.css',), files_list)

    def _create_fake_responses_for_gcs_bucket_create(self, resp):
        gcs_bucket_create_url = ''.join([
            'https://www.googleapis.com/storage/v1/b?project=', self._project_id
        ])
        gcs_bucket_create_body = json.dumps({
            'name': self._bucket_name,
            'location': 'US',
            'storageClass': 'multi_regional'
        })
        resp.add(
            resp.POST,
            gcs_bucket_create_url,
            body=gcs_bucket_create_body,
            content_type='application/json')

    @mock.patch('google.cloud.storage.Bucket.make_public', autoSpec=True)
    @responses.activate
    def test_create_gcs_bucket(self, unused_mock):
        self._create_fake_responses_for_gcs_bucket_create(responses)
        bucket = self._deploygke_workflow._create_gcs_bucket()
        self.assertEqual(self._bucket_name, bucket.name)

    def _create_fake_responses_for_gcs_upload(self, resp):
        gcs_upload_url = '/'.join([
            'https://www.googleapis.com/upload/storage/v1/b', self._bucket_name,
            'o'
        ])
        gcs_upload_response_body = json.dumps({
            'kind':
            'storage#object',
            'items': [
                {
                    'kind': 'storage#object',
                    'name': 'static/polls/style.css',
                    'bucket': self._bucket_name,
                    'contentType': 'text/css',
                    'storageClass': 'STANDARD'
                },
            ]
        })
        resp.add(
            resp.POST,
            gcs_upload_url,
            body=gcs_upload_response_body,
            content_type='application/json')

    @mock.patch('google.cloud.storage.Bucket.make_public', autoSpec=True)
    @responses.activate
    def test_upload_static_content_files(self, unused_mock):
        self._setup_django_files()
        self._create_fake_responses_for_gcs_bucket_create(responses)
        self._create_fake_responses_for_gcs_upload(responses)
        self._deploygke_workflow._collect_static_content()
        bucket = self._deploygke_workflow._create_gcs_bucket()
        file_paths = self._deploygke_workflow._upload_static_content(bucket)
        self.assertCountEqual(['static/polls/style.css'], file_paths)


class GetIngressUrlTest(absltest.TestCase):
    """Tests for deploygke.DeploygkeWorkflow._get_ingress_url()."""

    INGRESS_IP = '12.23.43.54'
    INGRESS_IP_URL = 'http://12.23.43.54/'

    INGRESS = (
        kubernetes.client.models.v1_load_balancer_ingress.V1LoadBalancerIngress(
            ip=INGRESS_IP))

    LOAD_BALANCER_WITH_INGRESS = (
        kubernetes.client.models.v1_load_balancer_status.V1LoadBalancerStatus(
            ingress=[INGRESS]))
    LOAD_BALANCER_NO_INGRESS = (
        kubernetes.client.models.v1_load_balancer_status.V1LoadBalancerStatus())

    STATUS_WITH_INGRESS = (
        kubernetes.client.models.v1_service_status.V1ServiceStatus(
            load_balancer=LOAD_BALANCER_WITH_INGRESS))
    STATUS_NO_INGRESS = (
        kubernetes.client.models.v1_service_status.V1ServiceStatus(
            load_balancer=LOAD_BALANCER_NO_INGRESS))

    SERVICE_WITH_INGRESS = kubernetes.client.models.v1_service.V1Service(
        'v1', status=STATUS_WITH_INGRESS)
    SERVICE_NO_INGRESS = kubernetes.client.models.v1_service.V1Service(
        'v1', status=STATUS_NO_INGRESS)

    def setUp(self):
        self._mock_load_kube_config = mock.patch(
            'kubernetes.config.load_kube_config')
        self._mock_load_kube_config.start()
        self.addCleanup(self._mock_load_kube_config.stop)

    def test_simple_success(self):
        with mock.patch(
                'kubernetes.client.CoreV1Api.list_service_for_all_namespaces',
                autoSpec=True) as mock_list_service_for_all_namespaces:
            mock_list_service_for_all_namespaces.return_value = (
                kubernetes.client.models.v1_service_list.V1ServiceList(
                    'v1', [self.SERVICE_WITH_INGRESS]))
            self.assertEqual(self.INGRESS_IP_URL,
                             deploygke.DeploygkeWorkflow._get_ingress_url())
            self.assertEqual(
                1, len(mock_list_service_for_all_namespaces.mock_calls))

    @mock.patch('time.sleep', autoSpec=True)
    def test_success_on_second_call(self, sleep):
        with mock.patch(
                'kubernetes.client.CoreV1Api.list_service_for_all_namespaces',
                autoSpec=True) as mock_list_service_for_all_namespaces:
            mock_list_service_for_all_namespaces.side_effect = [
                kubernetes.client.models.v1_service_list.V1ServiceList(
                    'v1', [self.SERVICE_NO_INGRESS]),
                kubernetes.client.models.v1_service_list.V1ServiceList(
                    'v1', [self.SERVICE_NO_INGRESS, self.SERVICE_WITH_INGRESS]),
            ]

            self.assertEqual(self.INGRESS_IP_URL,
                             deploygke.DeploygkeWorkflow._get_ingress_url())
            self.assertEqual(
                2, len(mock_list_service_for_all_namespaces.mock_calls))


class WaitForDeploymentReadyTest(absltest.TestCase):
    """Tests for deploygke.DeploygkeWorkflow._wait_for_deployment_ready()."""

    READY_REPLICAS = 3

    STATUS_READY = (
        kubernetes.client.models.extensions_v1beta1_deployment_status.
        ExtensionsV1beta1DeploymentStatus(ready_replicas=READY_REPLICAS))

    STATUS_NOT_READY = (
        kubernetes.client.models.extensions_v1beta1_deployment_status.
        ExtensionsV1beta1DeploymentStatus(ready_replicas=0))

    DEPLOYMENT_READY = (kubernetes.client.models.extensions_v1beta1_deployment.
                        ExtensionsV1beta1Deployment(status=STATUS_READY))

    DEPLOYMENT_NOT_READY = (
        kubernetes.client.models.extensions_v1beta1_deployment.
        ExtensionsV1beta1Deployment(status=STATUS_NOT_READY))

    def setUp(self):
        self._mock_load_kube_config = mock.patch(
            'kubernetes.config.load_kube_config')
        self._mock_load_kube_config.start()
        self.addCleanup(self._mock_load_kube_config.stop)
        project_id = project_name = 'deploygke_test'
        self._deploygke_workflow = deploygke.DeploygkeWorkflow(
            project_id, project_name, '')

    def test_simple_success(self):
        with mock.patch(
            ('kubernetes.client.ExtensionsV1beta1Api.'
             'list_deployment_for_all_namespaces'),
                autoSpec=True) as mock_list_deployment_for_all_namespaces:
            mock_list_deployment_for_all_namespaces.return_value = ((
                kubernetes.client.models.extensions_v1beta1_deployment_list.
                ExtensionsV1beta1DeploymentList(items=[self.DEPLOYMENT_READY])))
            self.assertEqual(
                self.READY_REPLICAS,
                self._deploygke_workflow._wait_for_deployment_ready())
            self.assertEqual(
                1, len(mock_list_deployment_for_all_namespaces.mock_calls))

    @mock.patch('time.sleep', autoSpec=True)
    def test_success_on_second_call(self, unused_sleep):
        with mock.patch(
            ('kubernetes.client.ExtensionsV1beta1Api.'
             'list_deployment_for_all_namespaces'),
                autoSpec=True) as mock_list_deployment_for_all_namespaces:
            mock_list_deployment_for_all_namespaces.side_effect = [
                (kubernetes.client.models.extensions_v1beta1_deployment_list.
                 ExtensionsV1beta1DeploymentList(
                     items=[self.DEPLOYMENT_NOT_READY])),
                (kubernetes.client.models.extensions_v1beta1_deployment_list.
                 ExtensionsV1beta1DeploymentList(
                     items=[self.DEPLOYMENT_NOT_READY, self.DEPLOYMENT_READY])),
            ]

            self.assertEqual(
                self.READY_REPLICAS,
                self._deploygke_workflow._wait_for_deployment_ready())
            self.assertEqual(
                2, len(mock_list_deployment_for_all_namespaces.mock_calls))
