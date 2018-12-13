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
from typing import Any, Dict, List, Optional
import webbrowser

from django_cloud_deploy import config
from django_cloud_deploy.cloudlib import billing
from django_cloud_deploy.skeleton import source_generator
from django_cloud_deploy.workflow import _database
from django_cloud_deploy.workflow import _deploygae
from django_cloud_deploy.workflow import _deploygke
from django_cloud_deploy.workflow import _enable_service
from django_cloud_deploy.workflow import _project
from django_cloud_deploy.workflow import _service_account
from django_cloud_deploy.workflow import _static_content_serve
import portpicker

from google.auth import credentials

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

    _TOTAL_NEW_STEPS = 8
    _TOTAL_UPDATE_STEPS = 3

    def __init__(self, credentials: credentials.Credentials, backend: str):
        self._source_generator = source_generator.DjangoSourceFileGenerator()
        self._billing_client = billing.BillingClient.from_credentials(
            credentials)
        self._project_workflow = _project.ProjectWorkflow(credentials)
        self._database_workflow = _database.DatabaseWorkflow(credentials)
        if backend == 'gke':
            self._deploygke_workflow = _deploygke.DeploygkeWorkflow(credentials)
        else:
            self._deploygae_workflow = _deploygae.DeploygaeWorkflow()
        self._enable_service_workflow = _enable_service.EnableServiceWorkflow(
            credentials)
        self._service_account_workflow = (
            _service_account.ServiceAccountKeyGenerationWorkflow(credentials))
        self._static_content_workflow = (
            _static_content_serve.StaticContentServeWorkflow(credentials))

    def create_and_deploy_new_project(
            self,
            project_name: str,
            project_id: str,
            project_creation_mode: ProjectCreationMode.CREATE,
            billing_account_name: str,
            django_project_name: str,
            django_app_name: str,
            django_superuser_name: str,
            django_superuser_email: str,
            django_superuser_password: str,
            django_directory_path: str,
            database_password: str,
            required_services: Optional[List[Dict[str, str]]] = None,
            required_service_accounts: Optional[
                Dict[str, List[Dict[str, Any]]]] = None,
            cloud_storage_bucket_name: str = None,
            region: str = 'us-west1',
            cloud_sql_proxy_path: str = 'cloud_sql_proxy',
            backend: str = 'gke',
            open_browser: bool = True):
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
            django_app_name: The name of the Django app e.g. "poll".
            django_superuser_name: The login name of the Django superuser e.g.
                "admin".
            django_superuser_email: The e-mail address of the Django superuser.
            django_superuser_password: The password of the Django superuser.
            django_directory_path: The location where the generated Django
                project code should be stored.
            database_password: The password for the default database user.
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
            cloud_storage_bucket_name: Name of the Google Cloud Storage Bucket
                we use to serve static content. By default it is equal to
                project id.
            region: Where the service is hosted.
            cloud_sql_proxy_path: The command to run your cloud sql proxy.
            backend: The desired backend to deploy the Django App on.
            open_browser: Whether we open the browser to show the deployed app
                at the end.

        Returns:
            The url of the deployed Django app.
        """

        # A bunch of variables necessary for deployment we hardcode for user.
        database_username = 'postgres'
        cloud_storage_bucket_name = cloud_storage_bucket_name or project_id

        sanitized_django_project_name = self._sanitize_name(django_project_name)
        cluster_name = sanitized_django_project_name
        database_name = sanitized_django_project_name + '-db'
        database_instance_name = sanitized_django_project_name + '-instance'

        image_name = '/'.join(
            ['gcr.io', project_id, sanitized_django_project_name])
        static_content_dir = os.path.join(django_directory_path, 'static')

        cloud_sql_proxy_port = portpicker.pick_unused_port()

        # TODO: Use progress bar to show status info instead of print statement
        print(
            self._generate_section_header(1, 'Create GCP Project',
                                          self._TOTAL_NEW_STEPS))
        self._project_workflow.create_project(project_name, project_id,
                                              project_creation_mode)

        print(
            self._generate_section_header(2, 'Billing Set Up',
                                          self._TOTAL_NEW_STEPS))
        if not self._billing_client.check_billing_enabled(project_id):
            self._billing_client.enable_project_billing(project_id,
                                                        billing_account_name)

        print(
            self._generate_section_header(3, 'Django Source Generation',
                                          self._TOTAL_NEW_STEPS))

        # Source generation requires service account ids.
        required_service_accounts = (
            required_service_accounts or
            self._service_account_workflow.load_service_accounts())
        cloud_sql_secrets, django_secrets = self._load_secret_names(
            required_service_accounts)
        self._source_generator.generate_all_source_files(
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
            cloudsql_secrets=cloud_sql_secrets,
            django_secrets=django_secrets,
            image_tag=image_name)

        print(
            self._generate_section_header(
                4, 'Database Set Up (Take Up To 5 Minutes)',
                self._TOTAL_NEW_STEPS))
        self._database_workflow.create_and_setup_database(
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

        print(
            self._generate_section_header(5, 'Enable Services',
                                          self._TOTAL_NEW_STEPS))
        if required_services is None:
            required_services = self._enable_service_workflow.load_services()
        self._enable_service_workflow.enable_required_services(
            project_id, required_services)

        print(
            self._generate_section_header(
                6, 'Static Content Serve Set Up (Take Up To 5 Minutes)',
                self._TOTAL_NEW_STEPS))
        self._static_content_workflow.serve_static_content(
            project_id, cloud_storage_bucket_name, static_content_dir)

        print(
            self._generate_section_header(
                7, 'Create Service Account Necessary For Deployment',
                self._TOTAL_NEW_STEPS))
        secrets = self._generate_secrets(project_id, database_username,
                                         database_password,
                                         required_service_accounts)

        if backend == 'gke':
            print(
                self._generate_section_header(
                    8, 'Deployment (Take Up To 20 Minutes)',
                    self._TOTAL_NEW_STEPS))
            app_url = self._deploygke_workflow.deploy_new_app_sync(
                project_id, cluster_name, django_directory_path,
                django_project_name, image_name, secrets)
        else:
            self._upload_secrets_to_bucket(project_id, secrets)
            print(
                self._generate_section_header(
                    8, 'Deployment (Take Up To 5 Minutes)',
                    self._TOTAL_NEW_STEPS))
            app_url = self._deploygae_workflow.deploy_gae_app(
                project_id, django_directory_path)

        # Create configuration file to save information needed in "update"
        # command.
        attributes = {
            'project_id': project_id,
            'django_project_name': django_project_name
        }
        self._save_config(django_directory_path, attributes)
        print('Your app is running at {}.'.format(app_url))

        if open_browser:
            webbrowser.open(app_url)
        return app_url

    def update_project(self,
                       django_directory_path: str,
                       database_password: str,
                       cloud_sql_proxy_path: str = 'cloud_sql_proxy',
                       region: str = 'us-west1',
                       open_browser: bool = True):
        """Workflow of updating a deployed Django app on GKE.

        Args:
            django_directory_path: The location where the generated Django
                project code should be stored.
            database_password: The password for the default database user.
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
        cloud_sql_proxy_port = portpicker.pick_unused_port()
        if not project_id or not django_project_name:
            raise InvalidConfigError(
                'Configuration file in [{}] does not contain enough '
                'information to update a Django project.'.format(
                    django_directory_path))

        # A bunch of variables necessary for deployment we hardcode for user.
        database_username = 'postgres'
        cloud_storage_bucket_name = project_id
        sanitized_django_project_name = self._sanitize_name(django_project_name)
        cluster_name = sanitized_django_project_name
        database_instance_name = sanitized_django_project_name + '-instance'
        image_name = '/'.join(
            ['gcr.io', project_id, sanitized_django_project_name])
        static_content_dir = os.path.join(django_directory_path, 'static')

        self._source_generator.setup_django_environment(
            django_directory_path, django_project_name, database_username,
            database_password, cloud_sql_proxy_port)
        print(
            self._generate_section_header(1, 'Database Migration',
                                          self._TOTAL_UPDATE_STEPS))
        self._database_workflow.migrate_database(
            project_id=project_id,
            instance_name=database_instance_name,
            cloud_sql_proxy_path=cloud_sql_proxy_path,
            region=region,
            port=cloud_sql_proxy_port)

        print(
            self._generate_section_header(2, 'Static Content Update',
                                          self._TOTAL_UPDATE_STEPS))
        self._static_content_workflow.update_static_content(
            cloud_storage_bucket_name, static_content_dir)

        print(
            self._generate_section_header(3, 'Update Deployment',
                                          self._TOTAL_UPDATE_STEPS))
        app_url = self._deploygke_workflow.update_app_sync(
            project_id, cluster_name, django_directory_path,
            django_project_name, image_name)
        print('Your app is running at {}.'.format(app_url))
        if open_browser:
            webbrowser.open(app_url)

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

    def _generate_section_header(self, step: int, section_name: str,
                                 total_steps: int):
        return '\n**Step {} of {}: {}**\n'.format(
            str(step), total_steps, section_name)

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
    def _load_secret_names(required_service_accounts: Optional[
            Dict[str, List[Dict[str, Any]]]] = None) -> (List[str], List[str]):
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

        Currently, only needed for database password.

        Generates JSON files that will be used by the django on GAE.

        Args:
              path: Path to create secret files to be uploaded.
              secrets: Contains the information regarding the credentials.
        """
        os.makedirs(path)
        secret_name = 'cloudsql'
        content = secrets['cloudsql']
        filename = '{}.json'.format(secret_name)
        file_path = os.path.join(path, filename)
        with open(file_path, 'w') as file:
            if secret_name == 'cloudsql':
                json.dump(content, file)
