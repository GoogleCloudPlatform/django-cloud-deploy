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
"""Tests for the cloudlib.project module."""

import subprocess
from unittest import mock

from absl.testing import absltest
from googleapiclient import errors

from django_cloud_deploy.cloudlib import project
from django_cloud_deploy.tests.unit.cloudlib.lib import http_fake


class OrganizationsFake(object):
    """A fake object returned by ...organizations()."""

    def __init__(self, is_google=False):
        self._is_google = is_google

    def search(self, body):
        if self._is_google:
            return http_fake.HttpRequestFake(
                {'organizations': [{
                    'displayName': 'google.com',
                }]})
        else:
            return http_fake.HttpRequestFake({})


class ProjectsFake(object):
    """A fake object returned by ...projects()."""

    def __init__(self):
        self.projects = []

    def create(self, body):
        for p in self.projects:
            if p['projectId'] == body['projectId']:
                return http_fake.HttpRequestFake(
                    errors.HttpError(http_fake.HttpResponseFake(409),
                                     b'Requested entity already exists'))
        self.projects.append(body)
        return http_fake.HttpRequestFake(
            {'name': 'operations/cp.7730969938063130608'})

    def get(self, projectId):
        for p in self.projects:
            if p['projectId'] == projectId:
                return http_fake.HttpRequestFake(p)
        return http_fake.HttpRequestFake(
            errors.HttpError(http_fake.HttpResponseFake(403),
                             b'permission denied'))


class ServiceFake:
    """A fake Resource returned by discovery.build('cloudresourcemanager', .."""

    def __init__(self, is_google=False):
        self.projects_fake = ProjectsFake()
        self.organizations_fake = OrganizationsFake(is_google)

    def projects(self):
        return self.projects_fake

    def organizations(self):
        return self.organizations_fake


class ProjectClientTestCase(absltest.TestCase):
    """Test case for project.ProjectClient."""

    def setUp(self):
        self._service_fake = ServiceFake()
        self._project_client = project.ProjectClient(self._service_fake)

    def test_create_project_non_googler(self):
        self._project_client.create_project('fn123', 'Friendly Name')
        self.assertEqual(self._service_fake.projects_fake.projects,
                         [{
                             'name': 'Friendly Name',
                             'projectId': 'fn123',
                         }])

    def test_create_project_googler(self):
        service_fake = ServiceFake(is_google=True)
        project_client = project.ProjectClient(service_fake)
        project_client.create_project('fn123', 'Friendly Name')
        self.assertEqual(service_fake.projects_fake.projects, [{
            'name': 'Friendly Name',
            'projectId': 'fn123',
            'parent': {
                'id': project._DEFAULT_GOOGLE_FOLDER_ID,
                'type': 'folder'
            }
        }])

    def test_create_project_exists(self):
        self._project_client.create_project('fn123', 'Friendly Name')
        with self.assertRaises(project.ProjectExistsError):
            self._project_client.create_project('fn123', 'Duplicate!')

    def test_project_exists_doesnot(self):
        self.assertFalse(self._project_client.project_exists('p123'))
