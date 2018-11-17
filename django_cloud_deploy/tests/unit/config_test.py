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
"""Unit test for django_cloud_deploy/config.py."""

import os
import shutil
import tempfile
import unittest

from django.core import management

from django_cloud_deploy import config


class ConfigurationTest(unittest.TestCase):
    """Unit test for django_cloud_deploy/config.py."""

    def setUp(self):
        # Create a temporary directory to put Django project files
        self._project_dir = tempfile.mkdtemp()

        # The configuration is expected to be generated under a Django project
        # directory. So we create all files for a Django project.
        management.call_command('startproject', 'mysite', self._project_dir)

    def tearDown(self):
        # Remove the directory after the test
        shutil.rmtree(self._project_dir)

    def test_create_configuration_file(self):
        configuration = config.Configuration(
            django_directory_path=self._project_dir)
        configuration.save()
        self.assertTrue(os.path.exists(configuration._config_path))

    def test_header_in_file(self):
        configuration = config.Configuration(
            django_directory_path=self._project_dir)
        configuration.save()
        with open(configuration._config_path) as config_file:
            self.assertIn(configuration._HEADER, config_file.read())

    def test_get_and_set(self):
        configuration = config.Configuration(
            django_directory_path=self._project_dir)
        configuration.set('var1', 'value1')
        configuration.set('var2', 2)
        configuration.set('list1', ['a', 'b'])
        configuration.set('dict1', {'a': 'b'})

        self.assertEqual(configuration.get('var1'), 'value1')
        self.assertEqual(configuration.get('var2'), 2)
        self.assertEqual(configuration.get('list1'), ['a', 'b'])
        self.assertEqual(configuration.get('dict1'), {'a': 'b'})
        self.assertIsNone(configuration.get('var3'))

    def test_get_after_save(self):
        configuration = config.Configuration(
            django_directory_path=self._project_dir)
        configuration.set('var1', 'value1')
        configuration.set('var2', 2)
        configuration.set('list1', ['a', 'b'])
        configuration.set('dict1', {'a': 'b'})
        configuration.save()

        configuration = config.Configuration(
            django_directory_path=self._project_dir)

        self.assertEqual(configuration.get('var1'), 'value1')
        self.assertEqual(configuration.get('var2'), 2)
        self.assertEqual(configuration.get('list1'), ['a', 'b'])
        self.assertEqual(configuration.get('dict1'), {'a': 'b'})
        self.assertIsNone(configuration.get('var3'))
