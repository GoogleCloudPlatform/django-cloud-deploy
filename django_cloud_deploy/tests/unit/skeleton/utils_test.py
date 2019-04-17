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


class GetDjangoProjectNameTest(unittest.TestCase):
    """Unit test for get_django_project_name."""

    def test_get_project_name(self):
        # Create a temporary directory to put Django project files
        project_dir = tempfile.mkdtemp()
        management.call_command('startproject', 'mysite', project_dir)
        self.assertEqual(utils.get_django_project_name(project_dir), 'mysite')
        shutil.rmtree(project_dir)

    def test_get_project_name_not_default_settings_module(self):
        # Create a temporary directory to put Django project files
        project_dir = tempfile.mkdtemp()
        management.call_command('startproject', 'mysite', project_dir)
        manage_py_path = os.path.join(project_dir, 'manage.py')
        with open(manage_py_path) as f:
            file_content = f.read()
            file_content = file_content.replace('mysite.settings',
                                                'mysite.settings.dev')
        with open(manage_py_path, 'wt') as f:
            f.write(file_content)
        self.assertEqual(utils.get_django_project_name(project_dir), 'mysite')
        shutil.rmtree(project_dir)

    def test_get_project_name_no_manage_py(self):
        # Create a temporary directory to put Django project files
        project_dir = tempfile.mkdtemp()
        self.assertIsNone(utils.get_django_project_name(project_dir))
        shutil.rmtree(project_dir)

    def test_manage_py_uses_variable_for_settings_module(self):
        """Test case for manage.py uses a variable for settings module."""
        project_dir = tempfile.mkdtemp()
        management.call_command('startproject', 'mysite', project_dir)
        manage_py_path = os.path.join(project_dir, 'manage.py')
        with open(manage_py_path) as f:
            file_content = f.read()
            file_content = file_content.replace('\'mysite.settings\'',
                                                'module_variable')
        with open(manage_py_path, 'wt') as f:
            f.write(file_content)
        self.assertIsNone(utils.get_django_project_name(project_dir))
        shutil.rmtree(project_dir)

    def test_get_project_name_invalid_manage_py(self):
        # Create a temporary directory to put Django project files
        project_dir = tempfile.mkdtemp()
        management.call_command('startproject', 'mysite', project_dir)
        manage_py_path = os.path.join(project_dir, 'manage.py')
        os.remove(manage_py_path)
        with open(manage_py_path, 'w') as f:
            f.write('12345')
        self.assertIsNone(utils.get_django_project_name(project_dir))
        shutil.rmtree(project_dir)


class IsValidDjangoProjectTest(unittest.TestCase):
    """Unit test for is_valid_django_project."""

    def test_valid_django_project(self):
        # Create a temporary directory to put Django project files
        project_dir = tempfile.mkdtemp()
        management.call_command('startproject', 'mysite', project_dir)
        self.assertTrue(utils.is_valid_django_project(project_dir))
        shutil.rmtree(project_dir)

    def test_invalid_django_project(self):
        # Create a temporary directory to put Django project files
        project_dir = tempfile.mkdtemp()
        self.assertFalse(utils.is_valid_django_project(project_dir))
        shutil.rmtree(project_dir)

    def test_invalid_manage_py(self):
        project_dir = tempfile.mkdtemp()
        management.call_command('startproject', 'mysite', project_dir)
        manage_py_path = os.path.join(project_dir, 'manage.py')
        os.remove(manage_py_path)
        with open(manage_py_path, 'w') as f:
            f.write('12345')
        self.assertFalse(utils.is_valid_django_project(project_dir))
        shutil.rmtree(project_dir)


class GuessRequirementsPathTest(unittest.TestCase):
    """Unit test for guess_requirements_path."""

    def setUp(self):
        super().setUp()
        self.project_dir = tempfile.mkdtemp()
        self.project_name = 'mysite'
        management.call_command('startproject', self.project_name,
                                self.project_dir)

    def tearDown(self):
        super().tearDown()
        shutil.rmtree(self.project_dir)

    def test_requirements_txt_exist(self):
        requirements_file_path = os.path.join(self.project_dir,
                                              'requirements.txt')
        with open(requirements_file_path, 'wt') as f:
            f.write('')
        self.assertEqual(
            utils.guess_requirements_path(self.project_dir, self.project_name),
            requirements_file_path)

    def test_requirements_txt_not_exist(self):
        self.assertIsNone(
            utils.guess_requirements_path(self.project_dir, self.project_name))

    def test_django_directory_not_exist(self):
        self.assertIsNone(
            utils.guess_requirements_path('directory_not_exist',
                                          self.project_name))

    def test_requirements_txt_exist_in_django_dir(self):
        requirements_file_path = os.path.join(self.project_dir,
                                              self.project_name,
                                              'requirements.txt')
        with open(requirements_file_path, 'wt') as f:
            f.write('')
        self.assertEqual(
            utils.guess_requirements_path(self.project_dir, self.project_name),
            requirements_file_path)

    def test_requirements_txt_exist_in_requirements_dir(self):
        requirements_dir = os.path.join(self.project_dir, 'requirements')
        os.mkdir(requirements_dir)
        requirements_file_path = os.path.join(requirements_dir, 'prod.txt')
        with open(requirements_file_path, 'wt') as f:
            f.write('')
        self.assertEqual(
            utils.guess_requirements_path(self.project_dir, self.project_name),
            requirements_file_path)


class GuessSettingsPath(unittest.TestCase):
    """Unit test for guess_settings_path of utils.py."""

    def setUp(self):
        super().setUp()
        self.project_name = 'mysite'
        self.project_dir = tempfile.mkdtemp()
        management.call_command('startproject', self.project_name,
                                self.project_dir)

    def tearDown(self):
        super().tearDown()
        shutil.rmtree(self.project_dir)

    def test_guess_default_settings_file(self):
        path = utils.guess_settings_path(self.project_dir)
        self.assertEqual(
            path,
            os.path.join(self.project_dir, self.project_name, 'settings.py'))

    def test_guess_prod_settings_file(self):
        settings_path = os.path.join(self.project_dir, self.project_name,
                                     'settings.py')
        prod_settings_path = os.path.join(self.project_dir, self.project_name,
                                          'settings_prod.py')
        shutil.copyfile(settings_path, prod_settings_path)
        self.assertEqual(utils.guess_settings_path(self.project_dir),
                         prod_settings_path)

    def test_manage_py_not_found(self):
        os.remove(os.path.join(self.project_dir, 'manage.py'))
        self.assertIsNone(utils.guess_settings_path(self.project_dir))

    def test_settings_module_in_manage_py_but_not_found(self):
        os.remove(
            os.path.join(self.project_dir, self.project_name, 'settings.py'))
        self.assertIsNone(utils.guess_settings_path(self.project_dir))

    def test_multiline_settings_module(self):
        manage_py_path = os.path.join(self.project_dir, 'manage.py')
        with open(manage_py_path) as f:
            file_content = f.read()

        with open(manage_py_path, 'wt') as f:
            file_content = file_content.replace(
                '\'{}.settings\''.format(self.project_name),
                ' \n      \'{}.settings\''.format(self.project_name))
            f.write(file_content)
        path = utils.guess_settings_path(self.project_dir)
        self.assertEqual(
            path,
            os.path.join(self.project_dir, self.project_name, 'settings.py'))

    def test_double_quotation_mark_for_module_name(self):
        manage_py_path = os.path.join(self.project_dir, 'manage.py')
        with open(manage_py_path) as f:
            file_content = f.read()

        with open(manage_py_path, 'wt') as f:
            file_content = file_content.replace(
                '\'{}.settings\''.format(self.project_name),
                '"{}.settings"'.format(self.project_name))
            f.write(file_content)
        path = utils.guess_settings_path(self.project_dir)
        self.assertEqual(
            path,
            os.path.join(self.project_dir, self.project_name, 'settings.py'))

    def test_settings_in_subdirectory(self):
        os.mkdir(os.path.join(self.project_dir, self.project_name, 'settings'))
        settings_path = os.path.join(self.project_dir, self.project_name,
                                     'settings.py')
        new_settings_path = os.path.join(self.project_dir, self.project_name,
                                         'settings', 'dev.py')
        shutil.move(settings_path, new_settings_path)
        prod_settings_path = os.path.join(self.project_dir, self.project_name,
                                          'settings', 'prod.py')
        shutil.copyfile(new_settings_path, prod_settings_path)
        manage_py_path = os.path.join(self.project_dir, 'manage.py')

        with open(manage_py_path) as f:
            file_content = f.read()
        with open(manage_py_path, 'wt') as f:
            file_content = file_content.replace(
                '{}.settings'.format(self.project_name),
                '{}.settings.dev"'.format(self.project_name))
            f.write(file_content)

        path = utils.guess_settings_path(self.project_dir)
        self.assertEqual(path, prod_settings_path)

    def test_use_variable_for_settings_module(self):
        manage_py_path = os.path.join(self.project_dir, 'manage.py')
        with open(manage_py_path) as f:
            file_content = f.read()

        with open(manage_py_path, 'wt') as f:
            file_content = file_content.replace(
                '\'{}.settings\''.format(self.project_name), 'module_variable')
            f.write(file_content)
        path = utils.guess_settings_path(self.project_dir)
        self.assertIsNone(path)
