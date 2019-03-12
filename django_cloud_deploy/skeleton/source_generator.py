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

"""Generate source files of a django app ready to be deployed to GKE."""

import os
import shutil
import sys
from typing import Any, Dict, List, Optional

import django
from django.core.management import utils
from django.utils import version
from django_cloud_deploy import crash_handling
import jinja2


class _FileGenerator(object):
    """An abstract class to generate files using templates."""

    def generate_from_existing(self):
        """Generate source files from existing files."""

    def generate_new(self):
        """Generate new source files."""

    def _get_template_folder_path(self) -> str:
        dirname, _ = os.path.split(os.path.abspath(__file__))
        return os.path.join(dirname, 'templates')

    @staticmethod
    def _delete_all_files(directory_path: str):
        """Delete all files under the given directory.

        Args:
            directory_path: Path to the directory to delete files.
        """
        for the_file in os.listdir(directory_path):
            file_path = os.path.join(directory_path, the_file)
            if os.path.isfile(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)


class _Jinja2FileGenerator(_FileGenerator):
    """A class to generate files with Jinja2."""

    REWRITE_TEMPLATE_SUFFIXES = (
        # Allow shipping invalid .py files without byte-compilation.
        ('.py-tpl', '.py'),
        ('.html-tpl', '.html'),
        ('.css-tpl', '.css'),)

    def __init__(self):
        self._template_env = jinja2.Environment()

    def _render_file(self,
                     template_path: str,
                     output_path: str,
                     options: Optional[Dict[str, Any]] = None):
        """Render a single file with template.

        Args:
            template_path: Absolute path of the template to render a file.
            output_path: Absolute path of the output file.
            options: Options used to render the file.
        """
        if not options:
            options = {}
        with open(template_path) as template_file:
            content = template_file.read()
        template = self._template_env.from_string(content)
        content = template.render(options)
        with open(output_path, 'w') as new_file:
            new_file.write(content)

    def _render_directory(self,
                          template_dir: str,
                          output_dir: str,
                          template_replacement: Optional[Dict[str, str]] = None,
                          options: Optional[Dict[str, Any]] = None):
        """Render all templates in a directory.

        Args:
            template_dir: Absolute path of the folder containing all template
                files.
            output_dir: Absolute path of the output folder.
            template_replacement: Strings in template file names to get replaced
                in the output.
            options: Options used to render the directory.
        """

        prefix_length = len(template_dir) + 1

        if not os.path.isdir(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        for root, _, files in os.walk(template_dir):
            path_rest = root[prefix_length:]
            if template_replacement:
                for before, after in template_replacement.items():
                    path_rest = path_rest.replace(before, after)
            relative_dir = path_rest
            if relative_dir:
                target_dir = os.path.join(output_dir, relative_dir)
                if not os.path.exists(target_dir):
                    os.mkdir(target_dir)

            for file_name in files:
                old_path = os.path.join(root, file_name)
                new_path = os.path.join(output_dir, relative_dir, file_name)
                for old_suffix, new_suffix in self.REWRITE_TEMPLATE_SUFFIXES:
                    if new_path.endswith(old_suffix):
                        new_path = new_path[:-len(old_suffix)] + new_suffix
                        break  # Only rewrite once
                self._render_file(old_path, new_path, options)

    def _generate_files(self, folder_name: str, destination: str,
                        filename_template_replacement=None, options=None):
        """Consolidates duplicate code that calls render_directory.

        Args:
            folder_name: Name of the folder that holds the templates
            destination: The destination path to hold files of the app.
            filename_template_replacement: Strings in template file names to
                get replaced in the output.
            options: Options used to render the directory.
        """
        if options is None:
            options = {}
        destination = os.path.abspath(os.path.expanduser(destination))
        templates_dir = os.path.join(self._get_template_folder_path(),
                                     folder_name)
        self._render_directory(templates_dir, destination,
                               filename_template_replacement, options)


class _DjangoProjectFileGenerator(_Jinja2FileGenerator):
    """Generate Django project files."""

    PROJECT_TEMPLATE_FOLDER = 'project_template'

    def generate_new(self, project_name: str, project_dir: str, app_name: str):
        """Generate django project files using our template.

        Args:
            project_name: Name of the project to be created.
            project_dir: The destination path to hold files of the project.
            app_name: The app that you want to create in your project.
        """
        options = {
            'app_name': app_name,
            'project_name': project_name,
            'docs_version': version.get_docs_version(),
        }
        filename_template_replacement = {
            'project_name': project_name,
        }
        self._generate_files(self.PROJECT_TEMPLATE_FOLDER, project_dir,
                             filename_template_replacement, options)


class _DjangoAppFileGenerator(_Jinja2FileGenerator):
    """Generate Django and app files."""

    APP_TEMPLATE_FOLDER = 'app_template'

    def generate_new(self, app_name: str, project_dir: str):
        """Generate django app files using our template.

        Args:
            app_name: Name of the app to be created.
            project_dir: Destination path to hold files of the app.
        """
        app_destination = os.path.join(project_dir, app_name)
        camel_case_value = ''.join(x for x in app_name.title() if x != '_')
        options = {
            'app_name': app_name,
            'camel_case_app_name': camel_case_value
        }
        self._generate_files(self.APP_TEMPLATE_FOLDER,
                             app_destination, options=options)


class _DjangoAdminOverwriteGenerator(_Jinja2FileGenerator):
    """Generate Django admin app overwrite files."""

    ADMIN_OVERWRITE_APP_NAME = 'cloud_admin'
    ADMIN_TEMPLATE_FOLDER = 'admin_template'
    TEMPLATES_TEMPLATE_FOLDER = 'templates_template'
    STATIC_TEMPLATE_FOLDER = 'static_template'

    def generate_new(self, project_id: str, project_name: str,
                     project_dir: str):
        self._generate_admin_files(project_id, project_name, project_dir)
        self._generate_templates_files(project_dir)
        self._generate_static_files(project_dir)

    def _generate_admin_files(self,
                              project_id: str,
                              project_name: str,
                              project_dir: str):
        """Create the django admin using our template.

        Args:
            project_id: The GCP project id.
            project_name: Name of the project to be created.
            project_dir: Destination path to hold files.
        """
        options = {
            'project_id': project_id,
            'project_name': project_name
        }
        admin_destination = os.path.join(project_dir,
                                         self.ADMIN_OVERWRITE_APP_NAME)
        self._generate_files(self.ADMIN_TEMPLATE_FOLDER,
                             admin_destination,
                             options=options)

    def _generate_templates_files(self, project_dir: str):
        """Create the django templates using our template.

        Args:
            project_dir: Destination path to hold files.
        """
        templates_destination = os.path.join(project_dir, 'templates')
        self._generate_files(self.TEMPLATES_TEMPLATE_FOLDER,
                             templates_destination)

    def _generate_static_files(self, project_dir: str):
        """Create our custom static files for the django app.

        Args:
            project_dir: Destination path to hold files.
        """
        static_destination = os.path.join(project_dir, 'staticfiles')
        self._generate_files(self.STATIC_TEMPLATE_FOLDER,
                             static_destination)


class _SettingsFileGenerator(_Jinja2FileGenerator):
    """Generate Django settings file."""

    _SETTINGS_TEMPLATE_DIRECTORY = 'settings_template'

    _FILES = ('base_settings.py', 'local_settings.py', 'cloud_settings.py')

    def generate_new(self,
                     project_id: str,
                     project_name: str,
                     project_dir: str,
                     cloud_sql_connection: str,
                     database_name: Optional[str] = None,
                     cloud_storage_bucket_name: Optional[str] = None):
        """Create Django settings file using our template.

        Args:
            project_id: GCP project id.
            project_name: Name of the project to be created.
            project_dir: The destination path to hold files of the project.
            cloud_sql_connection: Connection string to allow the django app
                to connect to the cloud sql proxy.
            database_name: Name of your cloud database.
            cloud_storage_bucket_name: Google Cloud Storage bucket name to
                serve static content.
        """
        database_name = database_name or project_name + '-db'
        destination = os.path.join(
            os.path.abspath(os.path.expanduser(project_dir)), project_name)
        cloud_storage_bucket_name = cloud_storage_bucket_name or project_id
        settings_templates_dir = os.path.join(self._get_template_folder_path(),
                                              self._SETTINGS_TEMPLATE_DIRECTORY)
        options = {
            'project_id': project_id,
            'project_name': project_name,
            'docs_version': version.get_docs_version(),
            'secret_key': utils.get_random_secret_key(),
            'database_name': database_name,
            'bucket_name': cloud_storage_bucket_name,
            'cloud_sql_connection': cloud_sql_connection
        }
        self._render_directory(settings_templates_dir, destination,
                               options=options)

    def generate_from_existing(self,
                               project_id: str,
                               project_name: str,
                               project_dir: str,
                               cloud_sql_connection: str,
                               database_name: Optional[str] = None,
                               cloud_storage_bucket_name:
                               Optional[str] = None):
        """Create Django settings file from an existing settings file.

        We made several assumptions:
            1. The existing settings file is in
               <project_dir>/<project_name>/settings.py
            2. There is only one settings file.

        This is achieved by rename the existing settings file to
        "base_settings.py", then create "local_settings.py" and
        "cloud_settings.py" from our templates. "local_settings.py" and
        "cloud_settings.py" inherits "base_settings.py", so the existing
        settings file still have effects, and we only override what we need to.

        Args:
            project_id: GCP project id.
            project_name: Name of the project to be created.
            project_dir: The destination path to hold files of the project.
            cloud_sql_connection: Connection string to allow the django app
                to connect to the cloud sql proxy.
            database_name: Name of your cloud database.
            cloud_storage_bucket_name: Google Cloud Storage bucket name to
                serve static content.
        """
        database_name = database_name or project_name + '-db'
        cloud_storage_bucket_name = cloud_storage_bucket_name or project_id

        settings_templates_dir = os.path.join(self._get_template_folder_path(),
                                              self._SETTINGS_TEMPLATE_DIRECTORY)
        django_dir = os.path.join(project_dir, project_name)

        # TODO: Make it smart enough to find settings file instead of hard
        # coding settings file path.
        settings_file_path = os.path.join(django_dir, 'settings.py')
        base_settings_path = os.path.join(django_dir, 'base_settings.py')
        options = {
            'project_id': project_id,
            'project_name': project_name,
            'docs_version': version.get_docs_version(),
            'secret_key': utils.get_random_secret_key(),
            'database_name': database_name,
            'bucket_name': cloud_storage_bucket_name,
            'cloud_sql_connection': cloud_sql_connection
        }
        self._render_directory(settings_templates_dir, django_dir,
                               options=options)
        os.replace(settings_file_path, base_settings_path)


class _DockerfileGenerator(_Jinja2FileGenerator):
    """Generate Dockerfile to build image for the Django project."""

    _FILES = ('Dockerfile', '.dockerignore')

    def generate_new(self, project_name: str, project_dir: str):
        """Generate Dockerfile and .dockerignore.

        Args:
            project_name: The name of your Django project.
            project_dir: The destination directory path to put Dockerfile.
        """
        file_names = ('Dockerfile', '.dockerignore')
        options = {'project_name': project_name}
        for file_name in file_names:
            template_path = os.path.join(self._get_template_folder_path(),
                                         file_name)
            output_path = os.path.join(project_dir, file_name)
            self._render_file(template_path, output_path, options)

    def generate_from_existing(self, project_name: str, project_dir: str):
        # TODO: Handle generation based on existing Dockerfile.
        self.generate_new(project_name, project_dir)


class _AppEngineFileGenerator(_Jinja2FileGenerator):
    """Generate App Engine Files for the Django project."""

    _FILES = ('.gcloudignore', 'app.yaml')

    def generate_new(self, project_name: str, project_dir: str,
                     service_name: Optional[str] = 'default'):
        """Generate app.yaml and .gcloudignore.

        Args:
            project_name: The name of your Django project.
            project_dir: The destination directory path to put Dockerfile.
            service_name: Name of App engine services.
                See https://cloud.google.com/appengine/docs/standard/python/an-overview-of-app-engine#services
        """
        self._generate_ignore(project_dir)
        self._generate_yaml(project_dir, project_name, service_name)

    def generate_from_existing(self, project_name: str, project_dir: str,
                               service_name: Optional[str] = 'default'):
        # TODO: Handle generation based on existing app.yaml
        self.generate_new(project_name, project_dir, service_name)

    def _generate_ignore(self, project_dir: str):
        file_name = '.gcloudignore'
        template_path = os.path.join(self._get_template_folder_path(),
                                     file_name)
        output_path = os.path.join(project_dir, file_name)
        self._render_file(template_path, output_path)

    def _generate_yaml(self, project_dir: str, project_name: str,
                       service_name: str):
        """Generate a yaml file to define how to deploy a Django app to GAE."""
        file_name = 'app.yaml'
        options = {
            'project_name': project_name,
            'service_name': service_name
        }
        template_path = os.path.join(self._get_template_folder_path(),
                                     file_name)
        output_path = os.path.join(project_dir, file_name)
        self._render_file(template_path, output_path, options)


class _DependencyFileGenerator(_Jinja2FileGenerator):
    """Generate dependencis needed by Django project."""

    _FILE = 'requirements.txt'

    def generate_new(self, project_dir: str):
        """Generate requirements.txt.

        Dependencies are hardcoded.

        Args:
            project_dir: The destination directory path to put requirements.txt.
        """

        # TODO: Find a way to determine the correct package version
        # instead of hardcoding everything.
        template_path = os.path.join(self._get_template_folder_path(),
                                     self._FILE)
        output_path = os.path.join(project_dir, self._FILE)
        self._render_file(template_path, output_path)

    def generate_from_existing(self, project_dir: str):
        # TODO: Handle generation based on existing requirements.txt
        self.generate_new(project_dir)


class _YAMLFileGenerator(_Jinja2FileGenerator):
    """Generate YAML file which defines Kubernete deployment and service."""

    def generate_new(self,
                     project_dir: str,
                     project_name: str,
                     project_id: str,
                     instance_name: Optional[str] = None,
                     region: Optional[str] = 'us-west1',
                     image_tag: Optional[str] = None,
                     cloudsql_secrets: Optional[List[str]] = None,
                     django_secrets: Optional[List[str]] = None):
        """Generate YAML file which defines Kubernete deployment and service.

        Args:
            project_dir: The destination directory path to put the yaml
                file.
            project_name: Name of your Django project.
            project_id: Your GCP project id. This can be got from your GCP
                console.
            instance_name: The name of cloud sql instance for
                database or the Django project. The default value for
                instance_name should be "{project_name}-instance".
            region: Where to host the Django project.
            image_tag: A customized docker image tag used in integration tests.
            cloudsql_secrets: A list of secrets needed by cloud sql proxy
                container.
            django_secrets: A list of secrets needed by Django app
                container.
        """
        file_name = 'project_name.yaml'
        image_tag = image_tag or '/'.join(['gcr.io', project_id, project_name])
        instance_name = instance_name or project_name + '-instance'

        # This string is used by cloud sql proxy and specifies how to connect to
        # your cloud sql instance.
        cloud_sql_connection_string = '{}:{}:{}'.format(project_id, region,
                                                        instance_name)
        cloudsql_secrets = cloudsql_secrets or ['cloudsql-oauth-credentials']
        django_secrets = django_secrets or []

        options = {
            'project_name': project_name,
            'project_id': project_id,
            'cloud_sql_connection_string': cloud_sql_connection_string,
            'image_tag': image_tag,
            'cloudsql_secrets': cloudsql_secrets,
            'django_secrets': django_secrets
        }
        template_path = os.path.join(self._get_template_folder_path(),
                                     file_name)
        output_path = os.path.join(project_dir, project_name + '.yaml')
        self._render_file(template_path, output_path, options)

    def generate_from_existing(self,
                               project_dir: str,
                               project_name: str,
                               project_id: str,
                               instance_name: Optional[str] = None,
                               region: Optional[str] = 'us-west1',
                               image_tag: Optional[str] = None,
                               cloudsql_secrets: Optional[List[str]] = None,
                               django_secrets: Optional[List[str]] = None):
        # Handle generation based on existing yaml files
        self.generate_new(project_dir, project_name, project_id,
                          instance_name, region, image_tag,
                          cloudsql_secrets, django_secrets)


class DjangoSourceFileGenerator(_FileGenerator):
    """The class to create all necessary Django source files."""

    def __init__(self):
        self.django_admin_overwrite_generator = _DjangoAdminOverwriteGenerator()
        self.django_app_generator = _DjangoAppFileGenerator()
        self.django_project_generator = _DjangoProjectFileGenerator()
        self.docker_file_generator = _DockerfileGenerator()
        self.dependency_file_generator = _DependencyFileGenerator()
        self.settings_file_generator = _SettingsFileGenerator()
        self.yaml_file_generator = _YAMLFileGenerator()
        self.app_engine_file_generator = _AppEngineFileGenerator()

    def setup_django_environment(self,
                                 project_dir: str,
                                 project_name: str,
                                 database_user: str,
                                 database_password: str,
                                 cloud_sql_proxy_port: Optional[int] = None):
        """Setup Django environment.

        This makes Django command calls afterwards affect the newly generated
        project.

        Args:
            project_dir: Absolute directory path to put your Django project.
            project_name: Name of your Django project.
            database_user: The name of the database user. By default it is
                "postgres". This is required for Django app to access database.
            database_password: The database password to set.
            cloud_sql_proxy_port: The port being forwarded by cloud sql proxy.
        """
        os.environ['DATABASE_USER'] = database_user
        os.environ['DATABASE_PASSWORD'] = database_password
        if cloud_sql_proxy_port:
            os.environ['CLOUD_SQL_PROXY_PORT'] = str(cloud_sql_proxy_port)
        sys.path.append(project_dir)
        os.environ['DJANGO_SETTINGS_MODULE'] = '{}.cloud_settings'.format(
            project_name)
        try:
            django.setup()
        except Exception as e:
            raise crash_handling.UserError(
                'Not able to import Django settings file.') from e

    def generate_new(self,
                     project_id: str,
                     project_name: str,
                     app_name: str,
                     project_dir: str,
                     database_user: str,
                     database_password: str,
                     cloud_sql_proxy_port: Optional[int] = None,
                     cloud_storage_bucket_name:
                     Optional[str] = None,
                     cloudsql_secrets: Optional[List[str]] = None,
                     django_secrets: Optional[List[str]] = None,
                     instance_name: Optional[str] = None,
                     database_name: Optional[str] = None,
                     region: Optional[str] = 'us-west1',
                     image_tag: Optional[str] = None,
                     service_name: Optional[str] = None):
        """Generate all source files of a Django app to be deployed to GCP.

        Args:
            project_id: Your GCP project id. This can be got from your GCP
                console.
            project_name: Name of your Django project.
            app_name: The app that you want to create in your project.
            project_dir: The destination directory path to put your Django
                project.
            database_user: The name of the database user. By default it is
                "postgres". This is required for Django app to access database.
            database_password: The database password to set.
            cloud_sql_proxy_port: The port being forwarded by cloud sql proxy.
            cloud_storage_bucket_name: Google Cloud Storage bucket name to
                serve static content.
            cloudsql_secrets: A list of secrets needed by cloud sql proxy
                container.
            django_secrets: A list of secrets needed by Django app
                container.
            instance_name: The name of cloud sql instance for database or the
                Django project. The default value for instance_name should be
                the project name.
            database_name: Name of your cloud database.
            region: Where to host the Django project.
            image_tag: A customized docker image tag used in integration tests.
            service_name: Name of App engine services. This is helpful in e2e
                test. See https://cloud.google.com/appengine/docs/standard/python/an-overview-of-app-engine#services
        """

        project_dir = os.path.abspath(os.path.expanduser(project_dir))
        os.makedirs(project_dir, exist_ok=True)

        # TODO: Ask users a question to make sure they really want to delete
        # all files in the given project directory
        self._delete_all_files(project_dir)

        instance_name = instance_name or project_name + '-instance'
        cloud_sql_connection_string = (
            '{}:{}:{}'.format(project_id, region, instance_name))
        self.django_project_generator.generate_new(
            project_name, project_dir, app_name)
        self.django_admin_overwrite_generator.generate_new(
            project_id, project_name, project_dir)
        self.django_app_generator.generate_new(app_name, project_dir)
        self.settings_file_generator.generate_new(
            project_id, project_name, project_dir, cloud_sql_connection_string,
            database_name, cloud_storage_bucket_name)
        self.docker_file_generator.generate_new(project_name, project_dir)
        self.dependency_file_generator.generate_new(project_dir)
        self.yaml_file_generator.generate_new(
            project_dir, project_name, project_id, instance_name, region,
            image_tag, cloudsql_secrets, django_secrets)
        self.app_engine_file_generator.generate_new(
            project_name, project_dir, service_name)
        self.setup_django_environment(
            project_dir=project_dir,
            project_name=project_name,
            database_user=database_user,
            database_password=database_password,
            cloud_sql_proxy_port=cloud_sql_proxy_port)

    def generate_from_existing(self,
                               project_id: str,
                               project_name: str,
                               project_dir: str,
                               database_user: str,
                               database_password: str,
                               cloud_sql_proxy_port: Optional[int] = None,
                               cloud_storage_bucket_name:
                               Optional[str] = None,
                               cloudsql_secrets: Optional[List[str]] = None,
                               django_secrets: Optional[List[str]] = None,
                               instance_name: Optional[str] = None,
                               database_name: Optional[str] = None,
                               region: Optional[str] = 'us-west1',
                               image_tag: Optional[str] = None,
                               service_name: Optional[str] = None):
        """Generate all source files of a Django app to be deployed to GCP.

        Args:
            project_id: Your GCP project id. This can be got from your GCP
                console.
            project_name: Name of your Django project.
            project_dir: The destination directory path to put your Django
                project.
            database_user: The name of the database user. By default it is
                "postgres". This is required for Django app to access database.
            database_password: The database password to set.
            cloud_sql_proxy_port: The port being forwarded by cloud sql proxy.
            cloud_storage_bucket_name: Google Cloud Storage bucket name to
                serve static content.
            cloudsql_secrets: A list of secrets needed by cloud sql proxy
                container.
            django_secrets: A list of secrets needed by Django app
                container.
            instance_name: The name of cloud sql instance for database or the
                Django project. The default value for instance_name should be
                the project name.
            database_name: Name of your cloud database.
            region: Where to host the Django project.
            image_tag: A customized docker image tag used in integration tests.
            service_name: Name of App engine services. This is helpful in e2e
                test. See https://cloud.google.com/appengine/docs/standard/python/an-overview-of-app-engine#services
        """
        project_dir = os.path.abspath(os.path.expanduser(project_dir))
        instance_name = instance_name or project_name + '-instance'
        cloud_sql_connection_string = (
            '{}:{}:{}'.format(project_id, region, instance_name))

        # We assume django admin overwrite files never exist in an existing
        # Django project
        self.django_admin_overwrite_generator.generate_new(
            project_id, project_name, project_dir)
        self.settings_file_generator.generate_from_existing(
            project_id, project_name, project_dir, cloud_sql_connection_string,
            database_name, cloud_storage_bucket_name)
        self.docker_file_generator.generate_from_existing(
            project_name, project_dir)
        self.dependency_file_generator.generate_from_existing(project_dir)
        self.yaml_file_generator.generate_from_existing(
            project_dir, project_name, project_id, instance_name, region,
            image_tag, cloudsql_secrets, django_secrets)
        self.app_engine_file_generator.generate_from_existing(
            project_name, project_dir, service_name)
        self.setup_django_environment(
            project_dir=project_dir,
            project_name=project_name,
            database_user=database_user,
            database_password=database_password,
            cloud_sql_proxy_port=cloud_sql_proxy_port)
