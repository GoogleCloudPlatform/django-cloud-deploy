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

from absl.testing import absltest

from django_cloud_deploy.skeleton import source_generator


class FileGeneratorTest(absltest.TestCase):

    def setUp(self):
        # Create a temporary directory to put Django project files
        self._project_dir = tempfile.mkdtemp()

    def tearDown(self):
        # Remove the directory after the test
        shutil.rmtree(self._project_dir)


class DjangoFileGeneratorTest(FileGeneratorTest):

    APP_ROOT_FOLDER_FILES = ('__init__.py', 'admin.py', 'apps.py', 'models.py',
                             'tests.py', 'views.py')
    PROJECT_ROOT_FOLDER_FILES = ('manage.py',)
    DJANGO_ROOT_FOLDER_FILES = ('__init__.py', 'base_settings.py',
                                'local_settings.py', 'urls.py', 'wsgi.py',
                                'remote_settings.py')

    @classmethod
    def setUpClass(cls):
        cls._django_file_generator = source_generator._DjangoFileGenerator()

    def test_project_root_structure(self):
        project_id = project_name = 'test_project_root'
        django_root_dir = os.path.join(self._project_dir, project_name)

        self._django_file_generator.generate_project_files(
            project_id, project_name, self._project_dir)
        self.assertTrue(os.path.exists(django_root_dir))

        files_list = os.listdir(self._project_dir)
        files_list.remove(project_name)
        self.assertCountEqual(self.PROJECT_ROOT_FOLDER_FILES, files_list)

    def test_django_root_structure(self):
        project_id = project_name = 'test_django_root'
        self._django_file_generator.generate_project_files(
            project_id, project_name, self._project_dir)

        files_list = os.listdir(os.path.join(self._project_dir, project_name))
        self.assertCountEqual(self.DJANGO_ROOT_FOLDER_FILES, files_list)

    def test_wsgi_module_uses_remote_settings(self):
        project_id = project_name = 'test_wsgi_module_uses_remote_settings'
        self._django_file_generator.generate_project_files(
            project_id, project_name, self._project_dir)

        with open(os.path.join(self._project_dir, project_name,
                               'wsgi.py')) as wsgi_file:
            wsgi_content = wsgi_file.read()

            # Test wsgi uses remote settings.
            self.assertIn('remote_settings', wsgi_content)

    def test_base_settings(self):
        project_id = project_name = 'test_base_settings'
        self._django_file_generator.generate_project_files(
            project_id, project_name, self._project_dir)

        with open(
                os.path.join(self._project_dir, project_name,
                             'base_settings.py')) as settings:
            settings_content = settings.read()

            # Test base settings generate secret keys.
            self.assertIn('SECRET_KEY', settings_content)

            # Test base settings does not setup database.
            self.assertNotIn('DATABASES', settings_content)

    def test_local_settings(self):
        project_id = project_name = 'test_local_settings'
        self._django_file_generator.generate_project_files(
            project_id, project_name, self._project_dir)

        with open(
                os.path.join(self._project_dir, project_name,
                             'local_settings.py')) as settings:
            settings_content = settings.read()

            # Test local settings imports base settings
            self.assertIn('base_settings', settings_content)

            # Test local settings use sqlite
            self.assertIn('sqlite3', settings_content)

            # Test local settings use DEBUG mode
            self.assertIn('DEBUG = True', settings_content)

            # Test local settings use local file systems to serve static files
            self.assertIn('STATIC_URL = \'/static/\'', settings_content)

    def test_remote_settings(self):
        project_name = 'test_remote_settings'
        project_id = project_name + 'project_id'
        self._django_file_generator.generate_project_files(
            project_id, project_name, self._project_dir)

        with open(
                os.path.join(self._project_dir, project_name,
                             'remote_settings.py')) as settings:
            settings_content = settings.read()

            # Test remote settings imports base settings
            self.assertIn('base_settings', settings_content)

            # Test remote settings use Postgres
            self.assertIn('postgresql', settings_content)

            # Test remote settings does not use DEBUG mode
            self.assertNotIn('DEBUG = True', settings_content)

            # Test remote settings use GCS buckets to serve static files
            self.assertIn(project_id + '/static', settings_content)

    def test_app_root_structure(self):
        app_name = 'test_app_root'
        app_folder_path = os.path.join(self._project_dir, app_name)
        self._django_file_generator.generate_app_files(app_name,
                                                       self._project_dir)
        self.assertTrue(os.path.exists(app_folder_path))

        files_list = os.listdir(app_folder_path)
        # Assert migrations folder exist
        self.assertIn('migrations', files_list)
        files_list.remove('migrations')
        self.assertCountEqual(self.APP_ROOT_FOLDER_FILES, files_list)


class DockerfileGeneratorTest(FileGeneratorTest):

    @classmethod
    def setUpClass(cls):
        cls._dockerfile_generator = source_generator._DockerfileGenerator()

    def test_generate_dockerfile(self):
        self._dockerfile_generator.generate('polls', self._project_dir)
        files_list = os.listdir(self._project_dir)
        self.assertIn('Dockerfile', files_list)
        self.assertIn('.dockerignore', files_list)

    def test_dockerfile_content(self):
        self._dockerfile_generator.generate('polls', self._project_dir)
        with open(os.path.join(self._project_dir, 'Dockerfile')) as dockerfile:
            dockerfile_content = dockerfile.read()

            # Test using python3 to create virtualenv
            self.assertIn('virtualenv -p python3', dockerfile_content)

            # Test using remote settings when deployed on GKE
            self.assertIn('remote_settings', dockerfile_content)

            # Test using gunicorn instead of Django builtin to run server
            self.assertIn('gunicorn', dockerfile_content)

            # Test generating correct wsgi module name.
            self.assertIn('polls.wsgi', dockerfile_content)


class DependencyFileGeneratorTest(FileGeneratorTest):

    @classmethod
    def setUpClass(cls):
        cls._dependency_generator = source_generator._DependencyFileGenerator()

    def test_generate_dependency_file(self):
        self._dependency_generator.generate(self._project_dir)
        files_list = os.listdir(self._project_dir)
        self.assertIn('requirements.txt', files_list)

    def test_dependencies(self):
        dependencies = ('Django==2.1.0', 'mysqlclient==1.3.13', 'wheel==0.31.1',
                        'gunicorn==19.9.0', 'psycopg2-binary==2.7.5')
        self._dependency_generator.generate(self._project_dir)
        dependency_file_path = os.path.join(self._project_dir,
                                            'requirements.txt')
        with open(dependency_file_path) as dependency_file:
            dependency_file_content = dependency_file.read()
            self.assertCountEqual(
                dependency_file_content.split('\n'), dependencies)


class YAMLFileGeneratorTest(FileGeneratorTest):

    @classmethod
    def setUpClass(cls):
        cls._yamlfile_generator = source_generator._YAMLFileGenerator()

    def test_generate_yaml_file(self):
        project_id = project_name = 'test_generate_yaml_file'
        self._yamlfile_generator.generate(self._project_dir, project_name,
                                          project_id)
        files_list = os.listdir(self._project_dir)
        self.assertIn(project_name + '.yaml', files_list)

    def test_yaml_file_content(self):
        project_id = project_name = 'test_generate_yaml_file'
        self._yamlfile_generator.generate(self._project_dir, project_name,
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


class DjangoSourceFileGeneratorTest(FileGeneratorTest):

    DOCKER_FILES = ('Dockerfile', '.dockerignore')
    DEPENDENCY_FILE = ('requirements.txt',)
    PROJECT_ROOT_FOLDER_FILES = ('manage.py',)

    @classmethod
    def setUpClass(cls):
        cls._file_generator = source_generator.DjangoSourceFileGenerator()

    def _test_project_structure(self, project_name, app_names, project_dir):
        files_list = os.listdir(project_dir)
        self.assertContainsSubset(self.PROJECT_ROOT_FOLDER_FILES, files_list)
        self.assertContainsSubset(self.DOCKER_FILES, files_list)
        self.assertContainsSubset(self.DEPENDENCY_FILE, files_list)
        self.assertContainsSubset(app_names, files_list)
        self.assertIn(project_name + '.yaml', files_list)
        self.assertIn(project_name, files_list)

    def test_generate_all_source_files(self):
        project_id = project_name = 'test_generate_all_source_file'
        app_names = ['polls1', 'polls2']
        self._file_generator.generate_all_source_files(
            project_id, project_name, app_names, self._project_dir)
        self._test_project_structure(project_name, app_names, self._project_dir)

    def test_file_generation_same_place(self):
        project_id = project_name = 'test_file_generation_same_place'
        app_names = ['polls1', 'polls2']

        # Test generating Django files at the same place multiple times.
        # This should not throw exceptions.
        for _ in range(3):
            self._file_generator.generate_all_source_files(
                project_id, project_name, app_names, self._project_dir)
        self._test_project_structure(project_name, app_names, self._project_dir)

    def test_file_generation_directory_not_exist(self):
        project_id = project_name = 'test_file_generation_same_place'
        app_names = ['polls1', 'polls2']

        project_dir = os.path.join(self._project_dir, 'dir_not_exist')
        self._file_generator.generate_all_source_files(project_id, project_name,
                                                       app_names, project_dir)
        self._test_project_structure(project_name, app_names, project_dir)
