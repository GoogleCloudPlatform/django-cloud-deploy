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

import importlib
import os
import shutil
import sys
import tempfile
import unittest

from absl.testing import absltest
from django.core import management

from django_cloud_deploy.skeleton import source_generator


class FileGeneratorTest(absltest.TestCase):

    def setUp(self):
        # Create a temporary directory to put Django project files
        self._project_dir = tempfile.mkdtemp()

    def tearDown(self):
        # Remove the directory after the test
        shutil.rmtree(self._project_dir)


class DjangoProjectFileGeneratorTest(FileGeneratorTest):

    PROJECT_ROOT_FOLDER_FILES = ('manage.py',)
    DJANGO_ROOT_FOLDER_FILES = ('__init__.py', 'urls.py', 'wsgi.py')

    @classmethod
    def setUpClass(cls):
        cls._generator = source_generator._DjangoProjectFileGenerator()

    def test_project_root_structure(self):
        project_name = 'test_project_root'
        django_root_dir = os.path.join(self._project_dir, project_name)
        app_name = 'test_app_name'

        self._generator.generate_new(project_name, self._project_dir, app_name)
        self.assertTrue(os.path.exists(django_root_dir))

        files_list = os.listdir(self._project_dir)
        files_list.remove(project_name)
        self.assertCountEqual(self.PROJECT_ROOT_FOLDER_FILES, files_list)

    def test_generate_new_files_twice(self):
        project_name = 'test_generate_files_twice'
        app_name = 'test_app_name'
        django_root_dir = os.path.join(self._project_dir, project_name)
        for _ in range(2):
            self._generator.generate_new(project_name, self._project_dir,
                                         app_name)
        self.assertTrue(os.path.exists(django_root_dir))

    def test_django_root_structure(self):
        project_name = 'test_django_root'
        app_name = 'test_app_name'
        self._generator.generate_new(project_name, self._project_dir, app_name)

        files_list = os.listdir(os.path.join(self._project_dir, project_name))
        self.assertCountEqual(self.DJANGO_ROOT_FOLDER_FILES, files_list)

    def test_wsgi_module_uses_cloud_settings(self):
        project_name = 'test_wsgi_module_uses_cloud_settings'
        app_name = 'test_app_name'
        self._generator.generate_new(project_name, self._project_dir, app_name)

        with open(os.path.join(self._project_dir, project_name,
                               'wsgi.py')) as wsgi_file:
            wsgi_content = wsgi_file.read()

            # Test wsgi uses remote settings.
            self.assertIn('cloud_settings', wsgi_content)

    def test_generate_project_files_from_existing_project(self):
        project_name = 'mysite'
        management.call_command('startproject', project_name, self._project_dir)
        settings_path = os.path.join(self._project_dir, project_name,
                                     'settings.py')
        self._generator.generate_from_existing(project_name, self._project_dir,
                                               settings_path)

        with open(os.path.join(self._project_dir, project_name,
                               'wsgi.py')) as f:
            content = f.read()

            # Test wsgi uses cloud settings.
            self.assertIn(project_name + '.cloud_settings', content)

    def test_wsgi_py_uses_variable_for_settings_module(self):
        project_name = 'mysite'
        management.call_command('startproject', project_name, self._project_dir)
        settings_path = os.path.join(self._project_dir, project_name,
                                     'settings.py')
        wsgi_path = os.path.join(self._project_dir, project_name, 'wsgi.py')
        with open(wsgi_path) as f:
            file_content = f.read()
        with open(wsgi_path, 'wt') as f:
            file_content = file_content.replace(
                '\'{}.settings\''.format(project_name), 'module_variable')
            f.write(file_content)
        self._generator.generate_from_existing(project_name, self._project_dir,
                                               settings_path)
        with open(wsgi_path) as f:
            content = f.read()
            # Test wsgi uses cloud settings.
            self.assertIn(project_name + '.cloud_settings', content)

    def test_settings_file_not_in_default_location(self):
        """Settings file is at <project_dir>/<project_name>/settings/dev.py."""
        project_name = 'mysite'
        management.call_command('startproject', project_name, self._project_dir)
        os.mkdir(os.path.join(self._project_dir, project_name, 'settings'))
        settings_path = os.path.join(self._project_dir, project_name,
                                     'settings.py')
        new_settings_path = os.path.join(self._project_dir, project_name,
                                         'settings', 'dev.py')
        shutil.move(settings_path, new_settings_path)
        self._generator.generate_from_existing(project_name, self._project_dir,
                                               new_settings_path)

        with open(os.path.join(self._project_dir, project_name,
                               'wsgi.py')) as f:
            content = f.read()

            # Test wsgi uses cloud settings.
            self.assertIn('mysite.settings.cloud_settings', content)


class DjangoAppFileGeneratorTest(FileGeneratorTest):

    APP_ROOT_FOLDER_FILES = ('__init__.py', 'admin.py', 'apps.py', 'models.py',
                             'tests.py', 'urls.py', 'views.py')

    @classmethod
    def setUpClass(cls):
        cls._generator = source_generator._DjangoAppFileGenerator()

    def test_app_root_structure(self):
        app_name = 'test_app_root'
        app_folder_path = os.path.join(self._project_dir, app_name)
        self._generator.generate_new(app_name, self._project_dir)
        self.assertTrue(os.path.exists(app_folder_path))

        files_list = os.listdir(app_folder_path)
        # Assert migrations folder exist
        self.assertIn('migrations', files_list)
        files_list.remove('migrations')
        self.assertCountEqual(self.APP_ROOT_FOLDER_FILES, files_list)

    def test_generate_app_twice(self):
        """Test app generation does not overwrite app with same name."""
        app_name = 'test_generate_app_twice'
        self._generator.generate_new(app_name, self._project_dir)

        # Generate an app and add customized files
        app_folder_path = os.path.join(self._project_dir, app_name)
        with open(os.path.join(app_folder_path, 'new_file'), 'w') as new_file:
            new_file.write('123')

        # Generate the same app again. This should not have any effects.
        self._generator.generate_new(app_name, self._project_dir)
        files_list = os.listdir(app_folder_path)
        self.assertIn('new_file', files_list)


class SettingsFileGeneratorTest(FileGeneratorTest):
    """Unit test for source_generator._SettingsFileGenerator."""

    @classmethod
    def setUpClass(cls):
        cls._generator = source_generator._SettingsFileGenerator()

    def test_settings(self):
        project_id = project_name = 'test_settings'
        cloud_sql_connection_string = ('{}:{}:{}'.format(
            project_id, 'us-west', 'instance'))
        self._generator.generate_new(project_id, project_name,
                                     self._project_dir,
                                     cloud_sql_connection_string)

        sys.path.append(self._project_dir)
        module = importlib.import_module(project_name + '.settings')

        # Test settings generate secret keys.
        self.assertIn('SECRET_KEY', dir(module))

        # Test settings use sqlite
        self.assertIn('sqlite3',
                      getattr(module, 'DATABASES')['default']['ENGINE'])

        # Test settings use DEBUG mode
        self.assertEqual(getattr(module, 'DEBUG'), True)

        # Test settings use local file systems to serve static files
        self.assertEqual(getattr(module, 'STATIC_URL'), '/static/')

    def test_cloud_settings_gke(self):
        project_name = 'test_cloud_settings_gke'
        project_id = project_name + 'project_id'
        cloud_sql_connection_string = ('{}:{}:{}'.format(
            project_id, 'us-west', 'instance'))
        self._generator.generate_new(project_id, project_name,
                                     self._project_dir,
                                     cloud_sql_connection_string)

        sys.path.append(self._project_dir)
        module = importlib.import_module(project_name + '.cloud_settings')

        # Test remote settings use postgresql
        self.assertIn('postgresql',
                      getattr(module, 'DATABASES')['default']['ENGINE'])

        # Test remote settings use the default database name
        self.assertEqual(project_name + '-db',
                         getattr(module, 'DATABASES')['default']['NAME'])

        # Test remote settings use default GCS buckets to serve static files
        self.assertIn(project_id + '/static', getattr(module, 'STATIC_URL'))

        # Test remote settings does not use DEBUG mode
        self.assertEqual(getattr(module, 'DEBUG'), False)

    def test_cloud_settings_gae(self):
        project_name = 'test_cloud_settings_gke'
        project_id = project_name + 'project_id'
        cloud_sql_connection_string = ('{}:{}:{}'.format(
            project_id, 'us-west', 'instance'))
        self._generator.generate_new(project_id, project_name,
                                     self._project_dir,
                                     cloud_sql_connection_string)
        settings_file_path = os.path.join(self._project_dir, project_name,
                                          'cloud_settings.py')

        # Not able to load the remote settings module because it runs
        # get_database_password() which does not work locally
        with open(settings_file_path) as settings:
            settings_content = settings.read()
            # Test cloud sql connection string is in host for GAE
            value = 'HOST\': \'/cloudsql/{}\''.format(
                cloud_sql_connection_string)
            self.assertIn(value, settings_content)

    def test_customize_cloud_settings(self):
        project_name = 'test_cloud_settings_customize_database_name'
        project_id = project_name + 'project_id'
        cloud_sql_connection_string = ('{}:{}:{}'.format(
            project_id, 'us-west', 'instance'))

        self._generator.generate_new(project_id, project_name,
                                     self._project_dir,
                                     cloud_sql_connection_string,
                                     'customize-db', 'customize-bucket')

        sys.path.append(self._project_dir)
        module = importlib.import_module(project_name + '.cloud_settings')

        # Test remote settings use postgresql
        self.assertIn('postgresql',
                      getattr(module, 'DATABASES')['default']['ENGINE'])

        # Test remote settings does not use DEBUG mode
        self.assertEqual(getattr(module, 'DEBUG'), False)

        # Test remote settings use GCS buckets to serve static files
        self.assertIn('customize-bucket/static', getattr(module, 'STATIC_URL'))

        # Test remote settings use the customized database name
        self.assertEqual('customize-db',
                         getattr(module, 'DATABASES')['default']['NAME'])

    def test_generate_settings_from_settings_generated_by_django_admin(self):
        project_name = 'test_generate_from_existing_settings'
        project_id = project_name + 'project_id'
        cloud_sql_connection_string = ('{}:{}:{}'.format(
            project_id, 'us-west', 'instance'))

        # Generate Django project files
        management.call_command('startproject', project_name, self._project_dir)
        django_settings_path = os.path.join(self._project_dir, project_name,
                                            'settings.py')
        self._generator.generate_from_existing(project_id, project_name,
                                               cloud_sql_connection_string,
                                               django_settings_path)

        expected_settings_files = ('settings.py', 'cloud_settings.py')
        files_list = os.listdir(os.path.join(self._project_dir, project_name))
        self.assertContainsSubset(expected_settings_files, files_list)

        sys.path.append(self._project_dir)

        # Test base settings
        module = importlib.import_module(project_name + '.settings')

        # Test base settings use sqlite
        self.assertIn('sqlite3',
                      getattr(module, 'DATABASES')['default']['ENGINE'])

        # Test base settings use DEBUG mode
        self.assertEqual(getattr(module, 'DEBUG'), True)

        # Test base settings use local file systems to serve static files
        self.assertEqual(getattr(module, 'STATIC_URL'), '/static/')

        # Test cloud settings
        module = importlib.import_module(project_name + '.cloud_settings')

        # Test cloud settings use postgresql
        self.assertIn('postgresql',
                      getattr(module, 'DATABASES')['default']['ENGINE'])

        # Test cloud settings use the default database name
        self.assertEqual(project_name + '-db',
                         getattr(module, 'DATABASES')['default']['NAME'])

        # Test cloud settings use default GCS buckets to serve static files
        self.assertIn(project_id + '/static', getattr(module, 'STATIC_URL'))

        # Test cloud settings does not use DEBUG mode
        self.assertEqual(getattr(module, 'DEBUG'), False)

    def test_cloud_settings_inherit_correct_settings(self):
        project_name = 'test_generate_from_existing_settings'
        project_id = project_name + 'project_id'
        cloud_sql_connection_string = ('{}:{}:{}'.format(
            project_id, 'us-west', 'instance'))

        # Generate Django project files
        management.call_command('startproject', project_name, self._project_dir)
        django_settings_path = os.path.join(self._project_dir, project_name,
                                            'settings.py')
        new_settings_path = os.path.join(self._project_dir, project_name,
                                         'local_settings.py')
        cloud_settings_path = os.path.join(self._project_dir, project_name,
                                           'cloud_settings.py')
        shutil.move(django_settings_path, new_settings_path)
        self._generator.generate_from_existing(project_id, project_name,
                                               cloud_sql_connection_string,
                                               new_settings_path)
        with open(cloud_settings_path) as settings:
            settings_content = settings.read()
            # Test cloud sql connection string is in host for GAE
            self.assertIn('from .local_settings import *', settings_content)


class DockerfileGeneratorTest(FileGeneratorTest):

    @classmethod
    def setUpClass(cls):
        cls._generator = source_generator._DockerfileGenerator()

    def test_generate_dockerfile(self):
        self._generator.generate_new('polls', self._project_dir)
        files_list = os.listdir(self._project_dir)
        self.assertIn('Dockerfile', files_list)
        self.assertIn('.dockerignore', files_list)

    def test_dockerfile_content(self):
        self._generator.generate_new('polls', self._project_dir)
        with open(os.path.join(self._project_dir, 'Dockerfile')) as dockerfile:
            dockerfile_content = dockerfile.read()

            # Test using python3 to create virtualenv
            self.assertIn('virtualenv -p python3', dockerfile_content)

            # Test using remote settings when deployed on GKE
            self.assertIn('cloud_settings', dockerfile_content)

            # Test using gunicorn instead of Django builtin to run server
            self.assertIn('gunicorn', dockerfile_content)

            # Test generating correct wsgi module name.
            self.assertIn('polls.wsgi', dockerfile_content)

    def test_generate_twice(self):
        self._generator.generate_new('polls', self._project_dir)
        self._generator.generate_new('polls', self._project_dir)
        files_list = os.listdir(self._project_dir)
        self.assertIn('Dockerfile', files_list)
        self.assertIn('.dockerignore', files_list)


class DependencyFileGeneratorTest(FileGeneratorTest):

    @classmethod
    def setUpClass(cls):
        cls._generator = source_generator._DependencyFileGenerator()

    def test_generate_dependency_file(self):
        self._generator.generate_new(self._project_dir)
        files_list = os.listdir(self._project_dir)
        self.assertIn(self._generator._REQUIREMENTS_GOOGLE, files_list)
        self.assertIn(self._generator._REQUIREMENTS, files_list)

    def test_generate_google_dependencies(self):
        # TODO: This is a change-detector test. It should be modified to not
        # check for exact dependencies.
        packages = ('Django', 'mysqlclient', 'wheel', 'gunicorn',
                    'psycopg2-binary', 'google-cloud-logging',
                    'google-cloud-storage', 'django-storages')
        self._generator.generate_new(self._project_dir)
        requirements_file_path = os.path.join(
            self._project_dir, self._generator._REQUIREMENTS_GOOGLE)
        with open(requirements_file_path) as f:
            file_content = f.read()
            for package in packages:
                self.assertIn(package, file_content)

    def test_generate_cloud_dependencies(self):
        self._generator.generate_new(self._project_dir)
        requirements_file_path = os.path.join(self._project_dir,
                                              self._generator._REQUIREMENTS)
        with open(requirements_file_path) as f:
            file_content = f.read()
            self.assertIn('-r ' + self._generator._REQUIREMENTS_GOOGLE,
                          file_content)

    def test_generate_cloud_dependencies_from_existing(self):
        project_name = 'test_cloud_dependencies_from_existing'
        packages = ['six', 'urllib3']
        # Create a Django project to make the directory looks similar with an
        # existing Django project
        management.call_command('startproject', project_name, self._project_dir)
        requirements_file_path = os.path.join(self._project_dir,
                                              self._generator._REQUIREMENTS)
        with open(requirements_file_path, 'wt') as f:
            f.write('\n'.join(packages))
        self._generator.generate_from_existing(self._project_dir,
                                               requirements_file_path)
        requirements_file_path = os.path.join(self._project_dir,
                                              self._generator._REQUIREMENTS)
        with open(requirements_file_path) as f:
            file_content = f.read()
            self.assertIn('-r ' + self._generator._REQUIREMENTS_GOOGLE,
                          file_content)
            self.assertIn('-r ' + self._generator._REQUIREMENTS_USER_RENAME,
                          file_content)

    def test_generate_cloud_dependencies_user_requirements_not_found(self):
        project_name = 'test_cloud_dependencies_from_existing'
        # Create a Django project to make the directory looks similar with an
        # existing Django project
        management.call_command('startproject', project_name, self._project_dir)
        self._generator.generate_from_existing(self._project_dir,
                                               '<path_not_exist>')
        requirements_file_path = os.path.join(self._project_dir,
                                              self._generator._REQUIREMENTS)
        with open(requirements_file_path) as f:
            file_content = f.read()
            self.assertIn('-r ' + self._generator._REQUIREMENTS_GOOGLE,
                          file_content)
            self.assertNotIn('-r ' + self._generator._REQUIREMENTS,
                             file_content)

    def test_generate_cloud_dependencies_duplicate_requirements(self):
        project_name = 'test_cloud_dependencies_from_existing'

        # "Django" is also a package required by us. We want to make sure
        # requirements-google.txt does not include this package
        packages = ['Django']

        # Create a Django project to make the directory looks similar with an
        # existing Django project
        management.call_command('startproject', project_name, self._project_dir)
        requirements_file_path = os.path.join(self._project_dir,
                                              self._generator._REQUIREMENTS)
        with open(requirements_file_path, 'wt') as f:
            f.write('\n'.join(packages))
        self._generator.generate_from_existing(self._project_dir,
                                               requirements_file_path)
        requirements_file_path = os.path.join(
            self._project_dir, self._generator._REQUIREMENTS_GOOGLE)
        with open(requirements_file_path) as f:
            file_content = f.read()
            self.assertNotIn('Django', file_content)

    def test_generate_cloud_dependencies_lower_case(self):
        project_name = 'test_cloud_dependencies_from_existing'

        # "Django" is also a package required by us. We want to make sure
        # requirements-google.txt does not include this package
        packages = ['django']
        management.call_command('startproject', project_name, self._project_dir)
        requirements_file_path = os.path.join(self._project_dir,
                                              self._generator._REQUIREMENTS)
        with open(requirements_file_path, 'wt') as f:
            f.write('\n'.join(packages))
        self._generator.generate_from_existing(self._project_dir,
                                               requirements_file_path)
        requirements_file_path = os.path.join(
            self._project_dir, self._generator._REQUIREMENTS_GOOGLE)
        with open(requirements_file_path) as f:
            file_content = f.read()
            self.assertNotIn('Django', file_content)

    def test_generate_requirements_in_subdirectory(self):
        # <django_directory>/requirements/prod.txt exist.
        # generate_from_existing should not rename this file
        project_name = 'test_generate_requirements_in_subdirectory'
        packages = ['six', 'urllib3']
        management.call_command('startproject', project_name, self._project_dir)
        requirements_dir = os.path.join(self._project_dir, 'requirements')
        os.mkdir(requirements_dir)
        user_requirements_file_path = os.path.join(requirements_dir, 'prod.txt')
        with open(user_requirements_file_path, 'wt') as f:
            f.write('\n'.join(packages))
        self._generator.generate_from_existing(self._project_dir,
                                               user_requirements_file_path)
        requirements_file_path = os.path.join(self._project_dir,
                                              self._generator._REQUIREMENTS)
        with open(requirements_file_path) as f:
            file_content = f.read()
            self.assertIn('-r ' + self._generator._REQUIREMENTS_GOOGLE,
                          file_content)
            self.assertNotIn('-r ' + self._generator._REQUIREMENTS,
                             file_content)
            self.assertIn('-r requirements/prod.txt', file_content)

    def test_generate_twice(self):
        self._generator.generate_new(self._project_dir)
        self._generator.generate_new(self._project_dir)
        files_list = os.listdir(self._project_dir)
        self.assertIn(self._generator._REQUIREMENTS, files_list)


class YAMLFileGeneratorTest(FileGeneratorTest):

    @classmethod
    def setUpClass(cls):
        cls._generator = source_generator._YAMLFileGenerator()

    def test_generate_yaml_file(self):
        project_id = project_name = 'test_generate_yaml_file'
        self._generator.generate_new(self._project_dir, project_name,
                                     project_id)
        files_list = os.listdir(self._project_dir)
        self.assertIn(project_name + '.yaml', files_list)

    def test_default_yaml_file_content(self):
        project_id = project_name = 'test_default_yaml_file_content'
        self._generator.generate_new(self._project_dir, project_name,
                                     project_id)

        yaml_file_path = os.path.join(self._project_dir, project_name + '.yaml')
        with open(yaml_file_path) as yaml_file:
            yaml_file_content = yaml_file.read()

            # Test cloud sql connection string is used in template rendering
            cloud_sql_connection_string = '{}:{}:{}'.format(
                project_id, 'us-west1', project_name + '-instance')
            self.assertIn(cloud_sql_connection_string, yaml_file_content)

            # Test docker image path is correct
            image_path = '/'.join(['gcr.io', project_id, project_name])
            self.assertIn(image_path, yaml_file_content)

            self.assertIn('kind: Deployment', yaml_file_content)
            self.assertIn('kind: Service', yaml_file_content)

            # Assert cloudsql secret is used as default
            self.assertIn('name: cloudsql-oauth-credentials', yaml_file_content)

    def test_lowercase_project_name(self):
        project_id = 'fake_projectid'
        project_name = 'DjangoBlog'
        self._generator.generate_new(self._project_dir, project_name,
                                     project_id)

        yaml_file_path = os.path.join(self._project_dir, project_name + '.yaml')
        with open(yaml_file_path) as yaml_file:
            yaml_file_content = yaml_file.read()
            self.assertIn(project_name.lower(), yaml_file_content)

    def test_customized_yaml_file_content(self):
        project_id = project_name = 'test_customized_yaml_file_content'
        instance_name = 'fake_instance_name'
        region = 'fake_region'
        image_tag = 'fake_image'
        cloudsql_secrets = ['fakecloudsql_secret1', 'fakecloudsql_secret2']
        django_secrets = ['fakedjango_app_secret1', 'fakedjango_app_secret2']
        self._generator.generate_new(self._project_dir, project_name,
                                     project_id, instance_name, region,
                                     image_tag, cloudsql_secrets,
                                     django_secrets)

        yaml_file_path = os.path.join(self._project_dir, project_name + '.yaml')
        with open(yaml_file_path) as yaml_file:
            yaml_file_content = yaml_file.read()

            # Test cloud sql connection string is used in template rendering
            cloud_sql_connection_string = '{}:{}:{}'.format(
                project_id, region, instance_name)
            self.assertIn(cloud_sql_connection_string, yaml_file_content)

            # Test docker image path is correct
            self.assertIn(image_tag, yaml_file_content)

            for secret in cloudsql_secrets:
                # Assert cloudsql secret is used
                self.assertIn('name: ' + secret, yaml_file_content)

            for secret in django_secrets:
                # Assert django_app secret is used
                self.assertIn('name: ' + secret, yaml_file_content)

    def test_generate_twice(self):
        project_id = project_name = 'test_generate_twice'
        self._generator.generate_new(self._project_dir, project_name,
                                     project_id)
        self._generator.generate_new(self._project_dir, project_name,
                                     project_id)
        files_list = os.listdir(self._project_dir)
        self.assertIn(project_name + '.yaml', files_list)


class DjangoSourceFileGeneratorTest(FileGeneratorTest):

    DOCKER_FILES = ('Dockerfile', '.dockerignore')
    DEPENDENCY_FILE = (
        source_generator._DependencyFileGenerator._REQUIREMENTS_GOOGLE,
        source_generator._DependencyFileGenerator._REQUIREMENTS)
    PROJECT_ROOT_FOLDER_FILES = ('manage.py',)
    SETTINGS_FILES = ('settings.py', 'cloud_settings.py')

    @classmethod
    def setUpClass(cls):
        cls._generator = source_generator.DjangoSourceFileGenerator()

    def _test_project_structure(self, project_name, app_name, project_dir):
        files_list = os.listdir(project_dir)
        self.assertContainsSubset(self.PROJECT_ROOT_FOLDER_FILES, files_list)
        self.assertContainsSubset(self.DOCKER_FILES, files_list)
        self.assertContainsSubset(self.DEPENDENCY_FILE, files_list)
        self.assertIn(app_name, files_list)
        self.assertIn(project_name + '.yaml', files_list)
        self.assertIn(project_name, files_list)

        files_list = os.listdir(os.path.join(project_dir, project_name))
        self.assertContainsSubset(self.SETTINGS_FILES, files_list)

    @unittest.mock.patch('subprocess.call')
    def test_generate_all_source_files(self, unused_mock):
        project_id = project_name = 'test_generate_all_source_file'
        app_name = 'polls'
        self._generator.generate_new(project_id, project_name, app_name,
                                     self._project_dir, 'fake_db_user',
                                     'fake_db_password')
        self._test_project_structure(project_name, app_name, self._project_dir)

    @unittest.mock.patch('subprocess.call')
    def test_delete_existing_files(self, unused_mock):
        project_id = project_name = 'test_delete_existing_files1'
        app_name = 'polls1'
        self._generator.generate_new(project_id, project_name, app_name,
                                     self._project_dir, 'fake_db_user',
                                     'fake_db_password')
        project_id = project_name = 'test_delete_existing_files2'
        self._generator.generate_new(project_id, project_name, app_name,
                                     self._project_dir, 'fake_db_user',
                                     'fake_db_password')
        self._test_project_structure(project_name, app_name, self._project_dir)
        files_list = os.listdir(os.path.join(self._project_dir, project_name))
        self.assertNotIn(project_name, files_list)

    @unittest.mock.patch('subprocess.call')
    def test_file_generation_same_place(self, unused_mock):
        project_id = project_name = 'test_file_generation_same_place'
        app_name = 'polls'

        # Test generating Django files at the same place multiple times.
        # This should not throw exceptions.
        for _ in range(3):
            self._generator.generate_new(project_id, project_name, app_name,
                                         self._project_dir, 'fake_db_user',
                                         'fake_db_password')
        self._test_project_structure(project_name, app_name, self._project_dir)

    @unittest.mock.patch('subprocess.call')
    def test_file_generation_directory_not_exist(self, unused_mock):
        project_id = project_name = 'test_file_generation_same_place'
        app_name = 'polls'

        project_dir = os.path.join(self._project_dir, 'dir_not_exist')
        self._generator.generate_new(project_id, project_name, app_name,
                                     project_dir, 'fake_db_user',
                                     'fake_db_password')
        self._test_project_structure(project_name, app_name, project_dir)

    @unittest.mock.patch('subprocess.call')
    def test_generate_missing_source_files(self, unused_mock):
        project_id = project_name = 'test_generate_missing_source_files'
        app_name = 'existing_app'
        management.call_command('startproject', project_name, self._project_dir)
        existing_app_path = os.path.join(self._project_dir, 'existing_app')
        os.mkdir(existing_app_path)
        management.call_command('startapp', app_name, existing_app_path)
        django_settings_path = os.path.join(self._project_dir, project_name,
                                            'settings.py')
        self._generator.generate_from_existing(
            project_id=project_id,
            project_name=project_name,
            project_dir=self._project_dir,
            django_settings_path=django_settings_path,
            database_user='fake_db_user',
            database_password='fake_db_password')
        self._test_project_structure(project_name, app_name, self._project_dir)
