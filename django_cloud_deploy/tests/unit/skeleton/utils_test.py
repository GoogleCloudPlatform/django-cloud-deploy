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
"""Unit test for django_cloud_deploy/skeleton/utils.py."""

import os
import shutil
import tempfile
import unittest

from django.core import management

from django_cloud_deploy.skeleton import utils


class UtilTest(unittest.TestCase):
    """Unit test for django_cloud_deploy/config.py."""

    def test_get_project_name(self):
        # Create a temporary directory to put Django project files
        project_dir = tempfile.mkdtemp()
        management.call_command('startproject', 'mysite', project_dir)
        self.assertEqual(utils.get_django_project_name(project_dir), 'mysite')
        shutil.rmtree(project_dir)

    def test_get_project_name_no_manage_py(self):
        # Create a temporary directory to put Django project files
        project_dir = tempfile.mkdtemp()
        with self.assertRaises(utils.ProjectContentError):
            utils.get_django_project_name(project_dir)
        shutil.rmtree(project_dir)

    def test_get_project_name_invalid_manage_py(self):
        # Create a temporary directory to put Django project files
        project_dir = tempfile.mkdtemp()
        management.call_command('startproject', 'mysite', project_dir)
        manage_py_path = os.path.join(project_dir, 'manage.py')
        os.remove(manage_py_path)
        with open(manage_py_path, 'w') as f:
            f.write('12345')
        with self.assertRaises(utils.ProjectContentError):
            utils.get_django_project_name(project_dir)
        shutil.rmtree(project_dir)
