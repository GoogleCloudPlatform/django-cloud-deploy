# Copyright 2018 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Tests for the cloudlib.container module."""

import base64
import json
from unittest import mock

from absl.testing import absltest

from django_cloud_deploy.cloudlib import container
from django_cloud_deploy.tests.unit.cloudlib.lib import http_fake
import google

PROJECT_ID = 'fake_project_id'
CLUSTER_NAME = 'fake_cluster'

FAKE_CA = b'123456'

CLUSTER_GET_RESPONSE_INVALID = """{
    "name": "invalid_cluster"
}"""

CLUSTER_GET_RESPONSE_TEMPLATE = """{{
    "name": "{}",
    "masterAuth": {{
        "clusterCaCertificate": "{}"
    }},
    "endpoint": "12.34.56.78",
    "status": "{}"
}}"""


class ClustersFake(object):

    def __init__(self):
        self.clusters_to_get_count = {}

    def create(self, projectId, zone, body):
        name = body['cluster']['name']
        if 'fail' not in name:
            if 'first' in name:
                # (current_get_count, total_get_count)
                self.clusters_to_get_count[name] = [0, 1]
            else:
                self.clusters_to_get_count[name] = [0, 2]
        return http_fake.HttpRequestFake(
            {'name': 'operations/cp.7730969938063130608'})

    def get(self, projectId, zone, clusterId):
        ca = base64.standard_b64encode(FAKE_CA).decode('utf-8')
        if 'invalid_response' in clusterId:
            return http_fake.HttpRequestFake(
                json.loads(CLUSTER_GET_RESPONSE_INVALID))
        if clusterId not in self.clusters_to_get_count:
            status = 'ERROR'
        else:
            self.clusters_to_get_count[clusterId][0] += 1
            get_count, total_get_count = self.clusters_to_get_count[clusterId]
            if get_count < total_get_count:
                status = 'PROVISIONING'
            else:
                status = 'RUNNING'
        response = CLUSTER_GET_RESPONSE_TEMPLATE.format(clusterId, ca, status)
        return http_fake.HttpRequestFake(json.loads(response))


class ZonesFake(object):

    def __init__(self):
        self.clusters_fake = ClustersFake()

    def clusters(self):
        return self.clusters_fake


class LocationsFake(object):

    def getServerConfig(self, name):
        del name
        return http_fake.HttpRequestFake(
            {'defaultClusterVersion': '1.9.7-gke.6'})


class ProjectsFake(object):

    def __init__(self):
        self.zones_fake = ZonesFake()
        self.locations_fake = LocationsFake()

    def zones(self):
        return self.zones_fake

    def locations(self):
        return self.locations_fake


class ContainerServiceFake(object):

    def __init__(self):
        self.projects_fake = ProjectsFake()

    def projects(self):
        return self.projects_fake


class ContainerClientTestCase(absltest.TestCase):
    """Test case for container.ContainerClient."""

    def setUp(self):
        mock_credentials = mock.Mock(spec=google.auth.credentials.Credentials)
        patcher = mock.patch('django_cloud_deploy.cloudlib.container.'
                             'ContainerClient._create_docker_client')
        self.addCleanup(patcher.stop)
        patcher.start()
        self._container_service = ContainerServiceFake()
        self._container_client = container.ContainerClient(
            self._container_service, mock_credentials)

    def test_create_cluster_simple_success(self):
        cluster_name = 'first_success'
        self._container_client.create_cluster_sync(PROJECT_ID, cluster_name)
        created_clusters = (self._container_service.projects_fake.zones_fake.
                            clusters_fake.clusters_to_get_count)
        self.assertIn(cluster_name, created_clusters)
        self.assertEqual(created_clusters[cluster_name][0], 1)

    def test_create_cluster_success_at_second_time(self):
        cluster_name = 'second_success'
        self._container_client.create_cluster_sync(PROJECT_ID, cluster_name)
        created_clusters = (self._container_service.projects_fake.zones_fake.
                            clusters_fake.clusters_to_get_count)
        self.assertIn(cluster_name, created_clusters)
        self.assertEqual(created_clusters[cluster_name][0], 2)

    def test_create_cluster_fail(self):
        cluster_name = 'fail'
        with self.assertRaises(container.ContainerCreationError):
            self._container_client.create_cluster_sync(PROJECT_ID, cluster_name)
        created_clusters = (self._container_service.projects_fake.zones_fake.
                            clusters_fake.clusters_to_get_count)
        self.assertNotIn(cluster_name, created_clusters)

    @mock.patch('google.auth.credentials.Credentials', autoSpec=True)
    def test_create_kubernetes_configuration_success(self, mock_credentials):
        mock_credentials.token = 'fake_token'
        kube_config = self._container_client.create_kubernetes_configuration(
            mock_credentials, PROJECT_ID, CLUSTER_NAME)
        self.assertEqual(kube_config.host, 'https://12.34.56.78')
        self.assertEqual(kube_config.api_key['authorization'],
                         mock_credentials.token)
        with open(kube_config.ssl_ca_cert, 'rb') as ca_file:
            self.assertEqual(ca_file.read(), FAKE_CA)
        self.assertEqual(kube_config.api_key_prefix['authorization'], 'Bearer')

    @mock.patch('google.auth.credentials.Credentials', autoSpec=True)
    def test_create_kubernetes_configuration_fail(self, mock_credentials):
        mock_credentials.token = 'fake_token'
        cluster_name = 'invalid_response'
        with self.assertRaises(container.ClusterGetInfoError):
            self._container_client.create_kubernetes_configuration(
                mock_credentials, PROJECT_ID, cluster_name)
