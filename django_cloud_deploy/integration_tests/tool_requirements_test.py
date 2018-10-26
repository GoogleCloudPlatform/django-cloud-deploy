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

"""Integration tests for tool_requirements.py."""
import os

from django_cloud_deploy import tool_requirements
from django_cloud_deploy.cli import io
from absl.testing import absltest


class ToolRequirementsNegativeTest(absltest.TestCase):
    """This will test all negative cases (not having the requirement)."""

    @classmethod
    def setUpClass(cls):
        """Modify the path to exclude the necesary requirments."""
        cls.temp_path = os.environ['PATH']
        os.environ['PATH'] = ''

    @classmethod
    def tearDownClass(cls):
        os.environ['PATH'] = cls.temp_path

    def setUp(self):
        self.test_console = io.TestIO()

    def requirement_missing(self, req: tool_requirements.Requirement):
        with self.assertRaises(
                tool_requirements.MissingRequirementsError) as cm:
            tool_requirements._REQUIREMENTS = [req]
            tool_requirements.check_and_handle_requirements(self.test_console)

        exception = cm.exception
        self.assertEqual(req.NAME,
                         exception.missing_requirements[0].name)

    def test_gcloud_missing(self):
        gcloud = tool_requirements.Gcloud
        self.requirement_missing(gcloud)

    def test_cloud_sql_proxy_missing(self):
        cloud_sql_proxy = tool_requirements.CloudSqlProxy
        self.test_console.answers.append('n')
        self.requirement_missing(cloud_sql_proxy)

    def test_docker_missing(self):
        docker = tool_requirements.Docker
        self.requirement_missing(docker)


class ToolRequirementsPositiveTest(absltest.TestCase):
    """This will test all positive cases (Having the requirement)."""

    def setUp(self):
        self.test_console = io.TestIO()

    def has_requirement(self, req: tool_requirements.Requirement):
        try:
            tool_requirements._REQUIREMENTS = [req]
            tool_requirements.check_and_handle_requirements(self.test_console)
        except tool_requirements.MissingRequirementsError:
            self.fail('Not suppose to be missing {}'.format(req.Name))

    def test_gcloud(self):
        Gcloud = tool_requirements.Gcloud
        self.has_requirement(Gcloud)

    def test_cloud_sql_proxy(self):
        cloud_sql_proxy = tool_requirements.CloudSqlProxy
        # This should only download once in our machine unless gcloud overrides
        self.test_console.answers.append('y')
        self.has_requirement(cloud_sql_proxy)

    def test_docker(self):
        docker = tool_requirements.Docker
        self.has_requirement(docker)


class ToolRequirementsHandleTest(absltest.TestCase):
    """This will test the handle functions of Requirements."""

    def setUp(self):
        self.test_console = io.TestIO()

    def has_requirement(self, req: tool_requirements.Requirement):
        try:
            req.check()
        except tool_requirements.MissingRequirementsError:
            self.fail('Not suppose to be missing {}'.format(req.Name))

    def test_cloud_sql_proxy_handle(self):
        cloud_sql_proxy = tool_requirements.CloudSqlProxy
        self.test_console.answers.append('y')
        cloud_sql_proxy.handle(self.test_console)
        self.has_requirement(cloud_sql_proxy)
