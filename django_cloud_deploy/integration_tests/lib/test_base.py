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

import os
import shutil
import tempfile
import yaml

from absl.testing import absltest
from google.oauth2 import service_account

import django_cloud_deploy.integration_tests
from django_cloud_deploy.integration_tests.lib import utils
from django_cloud_deploy.skeleton import source_generator


def _load_test_config():
    """Loads information of the pre-configured gcp project."""

    dirname, _ = os.path.split(
        os.path.abspath(django_cloud_deploy.integration_tests.__file__))
    config_path = os.path.join(dirname, 'data', 'integration_test_config.yaml')
    with open(config_path) as config_file:
        config_file_content = config_file.read()
    return yaml.load(config_file_content)


_TEST_CONFIG = _load_test_config()


class BaseTest(absltest.TestCase):
    """Base class for cloud django integration tests."""

    def setUp(self):
        self.service_account_key_path = os.environ.get(
            'GOOGLE_APPLICATION_CREDENTIALS')

        # The scopes are needed to generate tokens to access clusters on GKE.
        self.credentials = (
            service_account.Credentials.from_service_account_file(
                self.service_account_key_path,
                scopes=['https://www.googleapis.com/auth/cloud-platform']))

    @property
    def zone(self):
        return _TEST_CONFIG['zone']

    @property
    def project_id(self):
        return _TEST_CONFIG['project_id']

    @property
    def project_name(self):
        return _TEST_CONFIG['project_name']


class DjangoFileGeneratorTest(BaseTest):
    """Base class for test cases which need Django project files."""

    def setUp(self):
        super().setUp()
        self.project_dir = tempfile.mkdtemp()
        image_name = utils.get_resource_name(resource_type='image')
        self.image_tag = '/'.join(['gcr.io', self.project_id, image_name])
        app_names = ['fake_app']
        generator = source_generator.DjangoSourceFileGenerator()
        generator.generate_all_source_files(
            project_id=self.project_id,
            project_name=self.project_name,
            app_names=app_names,
            destination=self.project_dir,
            image_tag=self.image_tag)

    def tearDown(self):
        shutil.rmtree(self.project_dir)
