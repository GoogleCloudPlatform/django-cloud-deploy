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
"""Tests for the django_cloud_deploy.cli.google_client."""

from unittest import mock

from absl.testing import absltest

from django_cloud_deploy.cli import google_client as gc
from django_cloud_deploy.utils import workflow_io


class GoogleClientTest(absltest.TestCase):
    """Tests for google_client.GoogleClient."""

    @mock.patch('django_cloud_deploy.cloudlib.project.ProjectClient')
    def test_create_project_workflow(self, ProjectClient):
        project_client = ProjectClient()
        answers = ['My Project']
        google_client = gc.GoogleClient(
            workflow_io.Test(answers), project_client)

        returned_project_id = google_client.create_project_workflow()
        self.assertRegex(returned_project_id, r'my-project-\d{6}')

        self.assertEqual(1, project_client.create_and_set_project.call_count)
        (actual_project_id, actual_project_name), _ = (
            project_client.create_and_set_project.call_args)
        self.assertEqual('My Project', actual_project_name)
        self.assertRegex(actual_project_id, returned_project_id)
