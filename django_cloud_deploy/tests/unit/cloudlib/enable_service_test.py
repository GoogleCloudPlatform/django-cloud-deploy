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
"""Tests for the cloudlib.enable_service module."""

from absl.testing import absltest

from django_cloud_deploy.cloudlib import enable_service
from django_cloud_deploy.tests.unit.cloudlib.lib import http_fake

PROJECT_ID = 'fake_project_id'
SERVICE = 'fake_service'

ENABLED_SERVICE_RESPONSE = {
    'name': 'projects/{}/services/{}'.format(PROJECT_ID, SERVICE),
    'state': 'ENABLED'
}

DISABLED_SERVICE_RESPONSE = {
    'name': 'projects/{}/services/{}'.format(PROJECT_ID, SERVICE),
    'state': 'DISABLED'
}


class ServicesFake(object):

    def __init__(self, query_times=1):
        self.service_to_get_count = {}
        self._query_times = query_times
        self._get_times = 0

    def enable(self, name):
        self.service_to_get_count.setdefault(name, 0)
        return http_fake.HttpRequestFake(
            {'name': 'operations/cp.7730969938063130608'})

    def get(self, name):
        self.service_to_get_count[name] = (
            self.service_to_get_count.get(name, 0) + 1)
        self._get_times += 1
        if self._get_times >= self._query_times:
            return http_fake.HttpRequestFake(ENABLED_SERVICE_RESPONSE)
        else:
            return http_fake.HttpRequestFake(DISABLED_SERVICE_RESPONSE)


class ServiceUsageFake(object):

    def __init__(self, query_times=1):
        self.services_fake = ServicesFake(query_times)

    def services(self):
        return self.services_fake


class EnableServiceClientTestCase(absltest.TestCase):
    """Test case for project.ProjectClient."""

    def test_enable_service_simple_success(self):
        service_name = '/'.join(['projects', PROJECT_ID, 'services', SERVICE])
        mock_service = ServiceUsageFake()
        enable_service_client = enable_service.EnableServiceClient(mock_service)

        enable_service_client.enable_service_sync(PROJECT_ID, SERVICE)
        self.assertIn(service_name,
                      mock_service.services_fake.service_to_get_count)
        self.assertEqual(
            1, mock_service.services_fake.service_to_get_count[service_name])

    def test_enable_service_success_at_second_time(self):
        service_name = '/'.join(['projects', PROJECT_ID, 'services', SERVICE])
        mock_service = ServiceUsageFake(query_times=2)
        enable_service_client = enable_service.EnableServiceClient(mock_service)

        enable_service_client.enable_service_sync(PROJECT_ID, SERVICE)
        self.assertIn(service_name,
                      mock_service.services_fake.service_to_get_count)
        self.assertEqual(
            2, mock_service.services_fake.service_to_get_count[service_name])
