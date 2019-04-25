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
"""A module to manage workflow for deployment of Django apps."""

import json
import os
import shutil
import socket
from typing import Any, Dict, List, Optional, Tuple

from django_cloud_deploy import config
from django_cloud_deploy.cli import io
from django_cloud_deploy.cloudlib import billing
from django_cloud_deploy.skeleton import source_generator
from django_cloud_deploy.workflow import _database
from django_cloud_deploy.workflow import _enable_service
from django_cloud_deploy.workflow import deploy_workflow
from django_cloud_deploy.workflow import _project
from django_cloud_deploy.workflow import _service_account
from django_cloud_deploy.workflow import _static_content_serve
from django_cloud_deploy.workflow import _file_bucket
from django_cloud_deploy.utils import webbrowser

from google.auth import credentials
import portpicker

ProjectCreationMode = _project.CreationMode
ProjectExistsError = _project.ProjectExistsError

# Based on the source code of googleapiclient, the default timeout is 60
# seconds. This might not be enough and sometimes causing socket timeout
# exception.
# See https://github.com/googleapis/google-api-python-client/issues/563
socket.setdefaulttimeout(120)


class InvalidConfigError(Exception):
    """A error occurred when fail to read required information from config."""


class WorkflowManager(object):
    """A class to control workflow for deploying Django apps on GKE."""

    _TOTAL_NEW_STEPS = 9
    _TOTAL_UPDATE_STEPS = 3

    DEFAULT_GAE_SERVICE_NAME = 'default'

    def __init__(self, credentials: credentials.Credentials):
        self._source_generator = source_generator.DjangoSourceFileGenerator()
        self._billing_client = billing.BillingClient.from_credentials(
            credentials)
        self._project_workflow = _project.ProjectWorkflow(credentials)
        self._database_workflow = _database.DatabaseWorkflow(credentials)
        self.deploy_workflow = deploy_workflow.DeployWorkflow(credentials)
        self._enable_service_workflow = _enable_service.EnableServiceWorkflow(
            credentials)
        self._service_account_workflow = (
            _service_account.ServiceAccountKeyGenerationWorkflow(credentials))
        self._static_content_workflow = (
            _static_content_serve.StaticContentServeWorkflow(credentials))
        self._file_bucket_workflow = (
            _file_bucket.FileBucketCreationWorkflow(credentials))
        self._console_io = io.ConsoleIO()

    def create_and_deploy_new_project(
            self,
            project_name: str,
            project_id: str,
            project_creation_mode: ProjectCreationMode.CREATE,
            billing_account_name: str,
            django_project_name: str,
            django_superuser_name: str,
            django_superuser_email: str,
            django_superuser_password: str,
            django_directory_path: str,
            database_password: str,
            cluster_name: Optional[str] = None,
            database_instance_name: Optional[str] = None,
            django_app_name: Optional[str] = None,
            django_requirements_path: Optional[str] = None,
            django_settings_path: Optional[str] = None,
            required_services: Optional[List[Dict[str, str]]] = None,
            required_service_accounts: Optional[
                Dict[str, List[Dict[str, Any]]]] = None,
            appengine_service_name: Optional[str] = None,
            cloud_storage_bucket_name: str = None,
            file_storage_bucket_name: str = None,
            region: str = 'us-west1',
            cloud_sql_proxy_path: str = 'cloud_sql_proxy',
            backend: str = 'gke',
            open_browser: bool = True,
            deploy_existing_django_project: bool = False):
        """Workflow of deploying a newly generated Django app to GKE.

        Args:
            project_name: The name of the Google Cloud Platform project.
            project_id: The unique id to use when creating the Google Cloud
                Platform project.
            project_creation_mode: Whether we want to create the GCP project or
                use an existing project.
            billing_account_name: Name of the billing account user want to use
                for their Google Cloud Platform project. Should look like
                "billingAccounts/12345-678901-234567"
            django_project_name: The name of the Django project e.g. "mysite".
            django_superuser_name: The login name of the Django superuser e.g.
                "admin".
            django_superuser_email: The e-mail address of the Django superuser.
            django_superuser_password: The password of the Django superuser.
            django_directory_path: The location where the generated Django
                project code should be stored.
            database_password: The password for the default database user.
            cluster_name: Name of the cluster to use when deploying on GKE.
            database_instance_name: Name of the Cloud SQL instance to use for
                deployment
            django_app_name: The name of the Django app e.g. "poll". This is not
                needed in deploying existing projects because the projects
                already contain apps.
            django_requirements_path: Absolute path of requirements.txt of the
                existing Django project.
            django_settings_path: Absolute path of settings.py of the existing
                Django project.
            required_services: The services needed to be enabled for deployment.
            required_service_accounts: Service accounts needed to be created for
                deployment. It should have the following format:
                {
                    "cloud_sql": [{
                        "id": "service account id",
                        "name": "Display name",
                        "file_name": "credentials.json",
                        "roles": [
                            "roles/role1",
                            "roles/role2"
                        ]
                    }],
                }
            appengine_service_name: Name of App engine services. This is helpful
                in e2e test.
            cloud_storage_bucket_name: Name of the Google Cloud Storage Bucket
                we use to serve static content. By default it is equal to
                project id.
            file_storage_bucket_name: Name of the Google Cloud Storage Bucket
                used to store files by the Django app. By default it is equal to
                files-project id.
            region: Where the service is hosted.
            cloud_sql_proxy_path: The command to run your cloud sql proxy.
            backend: The desired backend to deploy the Django App on.
            open_browser: Whether we open the browser to show the deployed app
                at the end.
            deploy_existing_django_project: Whether this method is used to
                deploy an existing django project or not.

        Returns:
            The url of the deployed Django app.
        """
        # A bunch of variables necessary for deployment we hardcode for user.
        appengine_service_name = appengine_service_name or self.DEFAULT_GAE_SERVICE_NAME
        database_username = 'postgres'
        cloud_storage_bucket_name = cloud_storage_bucket_name or project_id
        file_storage_bucket_name = (file_storage_bucket_name or
                                    'files-{}'.format(project_id))

        sanitized_django_project_name = self._sanitize_name(django_project_name)
        cluster_name = cluster_name or sanitized_django_project_name
        database_name = sanitized_django_project_name + '-db'
        database_instance_name = (database_instance_name or
                                  sanitized_django_project_name + '-instance')
        django_settings_path = django_settings_path or os.path.join(
            django_directory_path, django_project_name, 'settings.py')
        django_requirements_path = django_requirements_path or os.path.join(
            django_directory_path, 'requirements.txt')
        image_name = '/'.join(
            ['gcr.io', project_id, sanitized_django_project_name])
        static_content_dir = os.path.join(django_directory_path, 'static')

        cloud_sql_proxy_port = portpicker.pick_unused_port()

        self._console_io.tell('[1/{}]: Create GCP Project'.format(
            self._TOTAL_NEW_STEPS))
        self._project_workflow.create_project(project_name, project_id,
                                              project_creation_mode)

        self._console_io.tell('[2/{}]: Billing Set Up'.format(
            self._TOTAL_NEW_STEPS))
        if not self._billing_client.check_billing_enabled(project_id):
            self._billing_client.enable_project_billing(project_id,
                                                        billing_account_name)

        self._console_io.tell('[3/{}]: Django Source Generation'.format(
            self._TOTAL_NEW_STEPS))
        # Source generation requires service account ids.
        required_service_accounts = (
            required_service_accounts or
            self._service_account_workflow.load_service_accounts())
        cloud_sql_secrets, django_secrets = self._load_secret_names(
            required_service_accounts)
        if deploy_existing_django_project:
            self._source_generator.generate_from_existing(
                project_id=project_id,
                project_name=django_project_name,
                project_dir=django_directory_path,
                database_user=database_username,
                database_password=database_password,
                django_requirements_path=django_requirements_path,
                django_settings_path=django_settings_path,
                instance_name=database_instance_name,
                database_name=database_name,
                cloud_sql_proxy_port=cloud_sql_proxy_port,
                cloud_storage_bucket_name=cloud_storage_bucket_name,
                file_storage_bucket_name=file_storage_bucket_name,
                cloudsql_secrets=cloud_sql_secrets,
                django_secrets=django_secrets,
                service_name=appengine_service_name,
                image_tag=image_name)
        else:
            self._source_generator.generate_new(
                project_id=project_id,
                project_name=django_project_name,
                app_name=django_app_name,
                project_dir=django_directory_path,
                database_user=database_username,
                database_password=database_password,
                instance_name=database_instance_name,
                database_name=database_name,
                cloud_sql_proxy_port=cloud_sql_proxy_port,
                cloud_storage_bucket_name=cloud_storage_bucket_name,
                file_storage_bucket_name=file_storage_bucket_name,
                cloudsql_secrets=cloud_sql_secrets,
                django_secrets=django_secrets,
                service_name=appengine_service_name,
                image_tag=image_name)

        with self._console_io.progressbar(
                300, '[4/{}]: Database Set Up'.format(self._TOTAL_NEW_STEPS)):
            self._database_workflow.create_and_setup_database(
                project_dir=django_directory_path,
                project_id=project_id,
                instance_name=database_instance_name,
                database_name=database_name,
                database_password=database_password,
                superuser_name=django_superuser_name,
                superuser_email=django_superuser_email,
                superuser_password=django_superuser_password,
                database_user=database_username,
                cloud_sql_proxy_path=cloud_sql_proxy_path,
                region=region,
                port=cloud_sql_proxy_port)

        with self._console_io.progressbar(
                180, '[5/{}]: Enable Services'.format(self._TOTAL_NEW_STEPS)):
            if required_services is None:
                required_services = (
                    self._enable_service_workflow.load_services())
            self._enable_service_workflow.enable_required_services(
                project_id, required_services)

        with self._console_io.progressbar(
                300, '[6/{}]: Static Content Serve Set Up'.format(
                    self._TOTAL_NEW_STEPS)):
            self._static_content_workflow.serve_static_content(
                project_id, cloud_storage_bucket_name, static_content_dir)

        self._console_io.tell('[7/{}]: File Bucket Creation'.format(
            self._TOTAL_NEW_STEPS))
        self._file_bucket_workflow.create_file_bucket(project_id,
                                                      file_storage_bucket_name)

        self._console_io.tell(
            '[8/{}]: Create Service Account Necessary For Deployment'.format(
                self._TOTAL_NEW_STEPS))
        secrets = self._generate_secrets(project_id, database_username,
                                         database_password,
                                         required_service_accounts)

        if backend == 'gke':
            with self._console_io.progressbar(
                    1200, '[9/{}]: Deployment'.format(self._TOTAL_NEW_STEPS)):
                app_url = self.deploy_workflow.deploy_gke_app(
                    project_id, cluster_name, django_directory_path,
                    django_project_name, image_name, secrets)
        else:
            self._upload_secrets_to_bucket(project_id, secrets)

            # If the app engine service name is not equal to 'default, then this
            # function is running in E2E test. In E2E test, a GAE application is
            # already created.
            is_new = appengine_service_name == self.DEFAULT_GAE_SERVICE_NAME
            with self._console_io.progressbar(
                    300, '[9/{}]: Deployment'.format(self._TOTAL_NEW_STEPS)):
                app_url = self.deploy_workflow.deploy_gae_app(
                    project_id, django_directory_path, is_new=is_new)
        self._static_content_workflow.set_cors_policy(cloud_storage_bucket_name,
                                                      app_url)
        # Create configuration file to save information needed in "update"
        # command.

        # Avoid showing the absolute path of settings file in configuration.
        relative_settings_path = os.path.relpath(django_settings_path,
                                                 django_directory_path)
        attributes = {
            'project_id': project_id,
            'django_project_name': django_project_name,
            'backend': backend,
            'django_settings_path': relative_settings_path,
        }
        self._save_config(django_directory_path, attributes)
        self._console_io.tell('Your app is running at {}.'.format(app_url))

        if open_browser:
            webbrowser.open_url(app_url)
        return app_url

    def update_project(self,
                       django_directory_path: str,
                       database_password: str,
                       cluster_name: Optional[str] = None,
                       database_instance_name: Optional[str] = None,
                       cloud_sql_proxy_path: str = 'cloud_sql_proxy',
                       region: str = 'us-west1',
                       open_browser: bool = True):
        """Workflow of updating a deployed Django app.

        Args:
            django_directory_path: The location where the generated Django
                project code should be stored.
            database_password: The password for the default database user.
            cluster_name: Name of the cluster to use when deploying on GKE.
            database_instance_name: Name of the Cloud SQL instance to use for
                deployment
            cloud_sql_proxy_path: The command to run your cloud sql proxy.
            region: Where the service is hosted.
            open_browser: Whether we open the browser to show the deployed app
                at the end.

        Raises:
            InvalidConfigError: When failed to read required information in the
                configuration file.
        """

        config_obj = config.Configuration(django_directory_path)
        project_id = config_obj.get('project_id')
        django_project_name = config_obj.get('django_project_name')
        backend = config_obj.get('backend')
        django_settings_path = config_obj.get('django_settings_path')
        if django_settings_path:
            django_settings_path = os.path.join(django_directory_path,
                                                django_settings_path)
        else:
            django_settings_path = os.path.join(django_directory_path,
                                                django_project_name,
                                                'settings.py')
        cloud_sql_proxy_port = portpicker.pick_unused_port()
        if not project_id or not backend or not django_project_name:
            raise InvalidConfigError(
                'Configuration file in [{}] does not contain enough '
                'information to update a Django project.'.format(
                    django_directory_path))

        # A bunch of variables necessary for deployment we hardcode for user.
        database_username = 'postgres'
        cloud_storage_bucket_name = project_id
        sanitized_django_project_name = self._sanitize_name(django_project_name)
        cluster_name = cluster_name or sanitized_django_project_name
        database_instance_name = (database_instance_name or
                                  sanitized_django_project_name + '-instance')
        image_name = '/'.join(
            ['gcr.io', project_id, sanitized_django_project_name])
        static_content_dir = os.path.join(django_directory_path, 'static')

        self._source_generator.setup_django_environment(django_directory_path,
                                                        database_username,
                                                        database_password,
                                                        django_settings_path,
                                                        cloud_sql_proxy_port)
        with self._console_io.progressbar(
                120,
                '[1/{}]: Database Migration'.format(self._TOTAL_UPDATE_STEPS)):
            self._database_workflow.migrate_database(
                project_dir=django_directory_path,
                project_id=project_id,
                instance_name=database_instance_name,
                cloud_sql_proxy_path=cloud_sql_proxy_path,
                region=region,
                port=cloud_sql_proxy_port)

        with self._console_io.progressbar(
                120, '[2/{}]: Static Content Update'.format(
                    self._TOTAL_UPDATE_STEPS)):
            self._static_content_workflow.update_static_content(
                cloud_storage_bucket_name, static_content_dir)

        with self._console_io.progressbar(
                180,
                '[3/{}]: Update Deployment'.format(self._TOTAL_UPDATE_STEPS)):
            if backend == 'gke':
                app_url = self.deploy_workflow.update_gke_app(
                    project_id, cluster_name, django_directory_path,
                    django_project_name, image_name)
            else:
                app_url = self.deploy_workflow.deploy_gae_app(
                    project_id, django_directory_path, is_new=False)
        self._console_io.tell('Your app is running at {}.'.format(app_url))
        if open_browser:
            webbrowser.open_url(app_url)

    @staticmethod
    def _sanitize_name(name: str) -> str:
        """Convert a python identifier to a valid GCP resource name.

        Args:
            name: The input name to convert.

        Returns:
            The GCP resource name converted from the given python identifier.
        """
        return name.replace('_', '-').lower()

    @staticmethod
    def _save_config(django_directory_path: str, attributes: Dict[str, Any]):
        config_obj = config.Configuration(django_directory_path)
        for key, value in attributes.items():
            config_obj.set(key, value)
        config_obj.save()

    def _generate_secrets(
            self, project_id: str, database_username: str,
            database_password: str,
            required_service_accounts: Dict[str, List[Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """Generate Kubernetes secrets required for deployment.

        Args:
            project_id: The unique id for your Google Cloud Platform project.
            database_username: Name of the default database user.
            database_password: The password for the default database user.
            required_service_accounts: Service accounts needed by deployment.

        Returns:
            All secrets necessary for deployment. For example:
                {
                    'cloudsql': {
                        'username': <database_username>,
                        'password': <database_password>
                    },
                    '<service_account_id1>': {
                        'credentials.json': <service_account_key_content>
                    }
                    '<service_account_id2>': {
                        'credentials.json': <service_account_key_content>
                    }
                }
        """

        secrets = {
            'cloudsql':
            self._generate_base_secrets(database_username, database_password)
        }

        for _, container_secrets in required_service_accounts.items():
            for s_a in container_secrets:
                key_data = (self._service_account_workflow.
                            create_service_account_and_key(
                                project_id, s_a['id'], s_a['name'],
                                s_a['roles']))
                secrets[s_a['id']] = {s_a['file_name']: key_data}
        return secrets

    @staticmethod
    def _generate_base_secrets(database_username: str,
                               database_password: str) -> Dict[str, str]:
        """Generates base secrets not related to service accounts.

        Args:
            database_username: Name of the database user.
            database_password: Password of the database.

        Returns:
            secrets: Base secret data used by kubernetes.
        """
        return {'username': database_username, 'password': database_password}

    @staticmethod
    def _load_secret_names(
            required_service_accounts: Dict[str, List[Dict[str, Any]]]
    ) -> Tuple[List[str], List[str]]:
        """Retrieves list of secret names for containers.

        Args:
            required_service_accounts: Service accounts needed by deployment.
        Returns:
            List of secrets for cloud_sql and django container.
        """
        cloud_sql_secrets = required_service_accounts.get('cloud_sql', [])
        django_secrets = required_service_accounts.get('django', [])
        cloud_sql_secrets = [sa['id'] for sa in cloud_sql_secrets]
        django_secrets = [sa['id'] for sa in django_secrets]
        return cloud_sql_secrets, django_secrets

    def _upload_secrets_to_bucket(self, project_id: str,
                                  secrets: Dict[str, Any]):
        """Creates files then uploads to GCP, finally removes the files.

        Args:
            project_id: Project to upload secret files to.
            secrets: Contains the information regarding the credentials.
        """
        # Create static dir for secrets
        secrets_dir = '~/.config/django_cloud/{}'.format(project_id)
        secrets_dir = os.path.abspath(os.path.expanduser(secrets_dir))
        self._create_files_for_secrets(secrets_dir, secrets)
        # Upload secrets to gcs bucket
        secrets_bucket_name = 'secrets-{}'.format(project_id)
        self._static_content_workflow.serve_secret_content(
            project_id, secrets_bucket_name, secrets_dir)
        shutil.rmtree(secrets_dir)

    @staticmethod
    def _create_files_for_secrets(path: str, secrets: Dict[str, Any]):
        """Create secret files for GAE that will be uploaded to GCS buckets.

        Generates JSON files that will be used by the django on GAE.

        Args:
              path: Path to create secret files to be uploaded.
              secrets: Contains the information regarding the credentials.
        """
        os.makedirs(path)
        for secret, content in secrets.items():
            filename = '{}.json'.format(secret)
            file_path = os.path.join(path, filename)
            with open(file_path, 'w') as file:
                json.dump(content, file)
