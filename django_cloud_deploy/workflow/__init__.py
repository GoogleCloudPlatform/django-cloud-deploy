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

import os
import webbrowser

from django_cloud_deploy.cloudlib import billing
from django_cloud_deploy.skeleton import source_generator
from django_cloud_deploy.workflow import _database
from django_cloud_deploy.workflow import _deploygke
from django_cloud_deploy.workflow import _enable_service
from django_cloud_deploy.workflow import _project
from django_cloud_deploy.workflow import _service_account
from django_cloud_deploy.workflow import _static_content_serve

from google.auth import credentials


class WorkflowManager(object):
    """A class to control workflow for deploying Django apps on GKE."""

    _TOTAL_NEW_STEPS = 8

    def __init__(self, credentials: credentials.Credentials):
        self._source_generator = source_generator.DjangoSourceFileGenerator()
        self._billing_client = billing.BillingClient.from_credentials(
            credentials)
        self._project_workflow = _project.ProjectWorkflow(credentials)
        self._database_workflow = _database.DatabaseWorkflow(credentials)
        self._deploygke_workflow = _deploygke.DeploygkeWorkflow(credentials)
        self._enable_service_workflow = _enable_service.EnableServiceWorkflow(
            credentials)
        self._service_account_workflow = (
            _service_account.ServiceAccountKeyGenerationWorkflow(credentials))
        self._statitc_content_workflow = (
            _static_content_serve.StaticContentServeWorkflow(credentials))

    def create_and_deploy_new_project(self,
                                      project_name: str,
                                      project_id: str,
                                      billing_account_name: str,
                                      django_project_name: str,
                                      django_app_name: str,
                                      django_superuser_name: str,
                                      django_superuser_email: str,
                                      django_superuser_password: str,
                                      django_directory_path: str,
                                      database_password: str,
                                      region: str = 'us-west1',
                                      cloud_sql_proxy_path: str =
                                      'cloud_sql_proxy',
                                      open_browser: bool = True):
        """Workflow of deploying a newly generated Django app to GKE.

        Args:
            project_name: The name of the Google Cloud Platform project.
            project_id: The unique id to use when creating the Google Cloud
                Platform project.
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
            region: Where the service is hosted.
            cloud_sql_proxy_path: The command to run your cloud sql proxy.
            open_browser: Whether we open the browser to show the deployed app
                at the end.
        """

        # A bunch of variables necessary for deployment we hardcode for user.
        database_username = 'postgres'
        cloud_storage_bucket_name = project_id
        cluster_name = django_project_name
        database_name = django_project_name + '-db'
        database_instance_name = django_project_name + '-instance'
        service_account_name = 'CloudSQL Oauth Credentials'
        service_account_id = 'cloudsql-oauth-credentials'

        service_account_key_path = (
            '{}/{}.json'.format(os.path.expanduser('~'), service_account_id))
        roles = (
            'roles/cloudsql.client', 'roles/cloudsql.editor',
            'roles/cloudsql.admin'
        )
        image_name = '/'.join(['gcr.io', project_id, django_project_name])
        static_content_dir = os.path.join(django_directory_path, 'static')

        # TODO: Use progress bar to show status info instead of print statement
        print(self._generate_section_header(1, 'Create GCP Project'))
        self._project_workflow.create_project(
            project_name, project_id)

        print(self._generate_section_header(2, 'Billing Set Up'))
        self._billing_client.enable_project_billing(
            project_id, billing_account_name)

        print(self._generate_section_header(3, 'Django Source Generation'))
        self._source_generator.generate_all_source_files(
            project_id=project_id,
            project_name=django_project_name,
            app_names=[django_app_name],
            destination=django_directory_path,
            database_user=database_username,
            database_password=database_password)

        print(self._generate_section_header(4, 'Database Set Up'))
        self._database_workflow.create_and_setup_database(
            project_id, database_instance_name, database_name,
            database_password, django_superuser_name, django_superuser_email,
            django_superuser_password, database_username,
            cloud_sql_proxy_path, region)

        print(self._generate_section_header(5, 'Enable Service\'s'))
        required_services = self._enable_service_workflow.load_services()
        self._enable_service_workflow.enable_required_services(
            project_id, required_services)

        print(self._generate_section_header(6, 'Static Content Serve Set Up'))
        self._statitc_content_workflow.serve_static_content(
            project_id, cloud_storage_bucket_name, static_content_dir)

        print(self._generate_section_header(
            7, 'Create Service Account Necessary For Deployment'))
        self._service_account_workflow.create_key(
            project_id, service_account_id, service_account_name, roles,
            service_account_key_path)

        # Prepare Kubernetes secret object based on service account key.
        with open(service_account_key_path) as key_file:
            key_content = key_file.read()
        secrets = {
            'cloudsql': {
                'username': database_username,
                'password': database_password
            },
            'cloudsql-oauth-credentials': {
                'credentials.json': key_content
            }
        }

        print(self._generate_section_header(8, 'Deployment'))
        admin_url = self._deploygke_workflow.deploy_new_app_sync(
            project_id, cluster_name, django_directory_path,
            django_project_name, image_name, secrets)
        if open_browser:
            webbrowser.open(admin_url)

    def _generate_section_header(self, step: str, section_name: str):
        return '\n**Step {} of {}: {}**\n'.format(
            step, self._TOTAL_NEW_STEPS, section_name)
