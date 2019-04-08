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
"""Integration tests for module django_cloud_deploy.workflow."""

import json
import os
import subprocess
import urllib.parse

from django_cloud_deploy.tests.lib import test_base
from django_cloud_deploy.tests.lib import utils
from django_cloud_deploy.workflow import _database
from django_cloud_deploy.workflow import _deploygke
from django_cloud_deploy.workflow import _enable_service
from django_cloud_deploy.workflow import _project
from django_cloud_deploy.workflow import _service_account
from django_cloud_deploy.workflow import _static_content_serve
from googleapiclient import discovery
from googleapiclient import errors
import requests


class EnableServiceWorkflowIntegrationTest(test_base.ResourceCleanUp,
                                           test_base.ResourceList):
    """Integration test for django_cloud_deploy.workflow._enable_service."""

    # Google drive api is not already enabled on the GCP project for integration
    # test.
    SERVICES = [{'title': 'Google Drive API', 'name': 'drive.googleapis.com'}]

    def setUp(self):
        super().setUp()
        self.enable_service_workflow = _enable_service.EnableServiceWorkflow(
            self.credentials)
        self.service_usage_service = discovery.build(
            'serviceusage',
            'v1',
            credentials=self.credentials,
            cache_discovery=False)

    def test_enable_services(self):
        with self.disable_services(self.SERVICES):
            self.enable_service_workflow.enable_required_services(
                project_id=self.project_id, services=self.SERVICES)
            enabled_services = self.list_enabled_services(
                self.service_usage_service)
            for service in self.SERVICES:
                self.assertIn(service['name'], enabled_services)


class ServiceAccountKeyGenerationWorkflowIntegrationTest(
        test_base.ResourceCleanUp, test_base.ResourceList):
    """Integration test for django_cloud_deploy.workflow._service_account."""

    ROLES = ('roles/cloudsql.client', 'roles/cloudsql.editor',
             'roles/cloudsql.admin')

    KEY_EXPECTED_ATTRIBUTES = ('type', 'project_id', 'private_key_id',
                               'private_key', 'client_email', 'client_id',
                               'auth_uri', 'token_uri',
                               'auth_provider_x509_cert_url',
                               'client_x509_cert_url')

    def setUp(self):
        super().setUp()
        self.service_account_workflow = (
            _service_account.ServiceAccountKeyGenerationWorkflow(
                self.credentials))
        self.iam_service = discovery.build('iam',
                                           'v1',
                                           credentials=self.credentials,
                                           cache_discovery=False)
        self.cloudresourcemanager_service = discovery.build(
            'cloudresourcemanager',
            'v1',
            credentials=self.credentials,
            cache_discovery=False)

    def _get_iam_policy(self):
        request = self.cloudresourcemanager_service.projects().getIamPolicy(
            resource=self.project_id)
        return request.execute(num_retries=5)

    def assert_valid_service_account_key(self, key):
        for attributes in self.KEY_EXPECTED_ATTRIBUTES:
            self.assertIn(attributes, key)
        self.assertEqual(self.project_id, key['project_id'])
        self.assertEqual('service_account', key['type'])

    def test_create_service_account_key(self):
        service_account_id = utils.get_resource_name(resource_type='sa')
        service_account_email = '{}@{}.iam.gserviceaccount.com'.format(
            service_account_id, self.project_id)
        member = 'serviceAccount:{}'.format(service_account_email)
        with self.delete_service_account(service_account_email):
            with self.reset_iam_policy(member, self.ROLES):
                key_data = (self.service_account_workflow.
                            create_service_account_and_key(
                                self.project_id, service_account_id,
                                'Test Service Account', self.ROLES))
                self.assert_valid_service_account_key(json.loads(key_data))

                # Assert the service account has correct roles
                policy = self._get_iam_policy()
                for role in self.ROLES:
                    find_role = False
                    for binding in policy['bindings']:
                        if binding['role'] == role:
                            find_role = True
                            self.assertIn(member, binding['members'])
                    self.assertTrue(find_role)


class DeploygkeWorkflowIntegrationTest(test_base.DjangoFileGeneratorTest,
                                       test_base.ResourceCleanUp):
    """Integration test for django_cloud_deploy.workflow._deploygke."""

    def setUp(self):
        super().setUp()
        self.deploygke_workflow = (_deploygke.DeploygkeWorkflow(
            self.credentials))

    def test_deploy_new_app_sync(self):
        cluster_name = utils.get_resource_name(resource_type='cluster')
        with open(self.service_account_key_path) as key_file:
            key_content = key_file.read()
        secrets = {
            'cloudsql': {
                'username': 'fake_db_user',
                'password': 'fake_db_password'
            },
            'cloudsql-oauth-credentials': {
                'credentials.json': key_content
            }
        }
        with self.clean_up_cluster(cluster_name):
            with self.clean_up_docker_image(self.image_tag):
                url = self.deploygke_workflow.deploy_new_app_sync(
                    project_id=self.project_id,
                    cluster_name=cluster_name,
                    app_directory=self.project_dir,
                    app_name=self.project_name,
                    image_name=self.image_tag,
                    secrets=secrets)
                admin_url = urllib.parse.urljoin(url, '/admin')
                response = requests.get(admin_url)
                self.assertIn('Django administration', response.text)


class ProjectWorkflowIntegrationTest(test_base.BaseTest):
    """Integration test for django_cloud_deploy.workflow._project."""

    def setUp(self):
        super().setUp()
        self._project_workflow = _project.ProjectWorkflow(self.credentials)

    def test_create_new_project_no_permission(self):
        project_name = 'New Project'
        project_id = utils.get_resource_name(resource_type='project')

        exception_regex = r'.*HttpError 403.*'

        # The provided credentials object does not have permission to create
        # projects
        with self.assertRaisesRegex(errors.HttpError, exception_regex):
            self._project_workflow.create_project(project_name, project_id)

    def test_create_new_project_must_exist(self):
        project_name = 'New Project'
        project_id = utils.get_resource_name(resource_type='project')

        exception_regex = r'.*does not exist.*'

        with self.assertRaisesRegex(_project.ProjectionCreationError,
                                    exception_regex):
            self._project_workflow.create_project(
                project_name,
                project_id,
                project_creation=_project.CreationMode.MUST_EXIST)

    def test_create_new_project_already_exist(self):
        exception_regex = r'.*already exists.*'

        with self.assertRaisesRegex(_project.ProjectionCreationError,
                                    exception_regex):
            self._project_workflow.create_project(
                self.project_name,
                self.project_id,
                project_creation=_project.CreationMode.CREATE)

    def test_create_new_project_already_exist_create_if_needed(self):
        self._project_workflow.create_project(
            self.project_name,
            self.project_id,
            project_creation=_project.CreationMode.CREATE_IF_NEEDED)
        output = subprocess.check_output([
            'gcloud', 'config', 'list', 'project', '--format=csv(core.project)'
        ],
                                         universal_newlines=True)
        self.assertIn(self.project_id, output)


class StaticContentServeWorkflowIntegrationTest(
        test_base.DjangoFileGeneratorTest, test_base.ResourceCleanUp):
    """Integration test for django_gke.workflow._static_content_serve."""

    def setUp(self):
        super().setUp()
        self._static_content_serve_workflow = (
            _static_content_serve.StaticContentServeWorkflow(self.credentials))

    def test_serve_static_content(self):
        bucket_name = utils.get_resource_name('bucket')
        static_content_dir = os.path.join(self.project_dir, 'static')
        with self.clean_up_bucket(bucket_name):
            self._static_content_serve_workflow.serve_static_content(
                self.project_id, bucket_name, static_content_dir)
            object_path = 'static/admin/css/base.css'
            object_url = 'http://storage.googleapis.com/{}/{}'.format(
                bucket_name, object_path)
            response = requests.get(object_url)
            self.assertIn('DJANGO', response.text)


class DatabaseWorkflowIntegrationTest(test_base.DjangoFileGeneratorTest,
                                      test_base.ResourceCleanUp,
                                      test_base.ResourceList):
    """Integration test for django_cloud_deploy.workflow._database."""

    def setUp(self):
        super().setUp()
        self.database_workflow = _database.DatabaseWorkflow(self.credentials)
        self.sqladmin_service = discovery.build('sqladmin',
                                                'v1beta4',
                                                cache_discovery=False,
                                                credentials=self.credentials)

    def test_create_and_setup_database(self):
        """Test case for _database.DatabaseWorkflow.create_and_setup_database.

        This test also tests _database.DatabaseWorkflow.migrate_database.
        migrate_database is a part of create_and_setup_database.
        """
        with self.clean_up_sql_instance(self.instance_name):
            with self.clean_up_database(self.instance_name, self.database_name):
                superuser_name = 'admin'
                superuser_email = 'admin@gmail.com'
                superuser_password = 'fake_superuser_password'

                self.database_workflow.create_and_setup_database(
                    project_dir=self.project_dir,
                    project_id=self.project_id,
                    instance_name=self.instance_name,
                    database_name=self.database_name,
                    database_password=self.database_password,
                    superuser_name=superuser_name,
                    superuser_email=superuser_email,
                    superuser_password=superuser_password)

                # Assert Cloud SQL instance is created
                instances = self.list_instances(self.sqladmin_service)
                self.assertIn(self.instance_name, instances)

                # Assert database is created
                databases = self.list_databases(self.instance_name,
                                                self.sqladmin_service)
                self.assertIn(self.database_name, databases)

                with self.database_workflow.with_cloud_sql_proxy(
                        self.project_id, self.instance_name):
                    # # This can only be imported after django.setup() is called
                    from django.contrib.auth.models import User

                    # Assert superuser is created
                    users = User.objects.filter(username=superuser_name)
                    self.assertEqual(len(users), 1)
                    user = users[0]
                    self.assertTrue(user.is_superuser)
