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

import contextlib
import json
import os
import subprocess
import tempfile

from django_cloud_deploy.integration_tests.lib import test_base
from django_cloud_deploy.integration_tests.lib import utils
from django_cloud_deploy.workflow import _database
from django_cloud_deploy.workflow import _deploygke
from django_cloud_deploy.workflow import _enable_service
from django_cloud_deploy.workflow import _project
from django_cloud_deploy.workflow import _service_account
from django_cloud_deploy.workflow import _static_content_serve
from googleapiclient import discovery
from googleapiclient import errors
import requests


class EnableServiceWorkflowIntegrationTest(test_base.BaseTest):
    """Integration test for django_cloud_deploy.workflow._enable_service."""

    # Google drive api is not already enabled on the GCP project for integration
    # test.
    SERVICES = [{'title': 'Google Drive API', 'name': 'drive.googleapis.com'}]

    def setUp(self):
        super().setUp()
        self.enable_service_workflow = _enable_service.EnableServiceWorkflow(
            self.credentials)
        self.service_usage_service = discovery.build(
            'serviceusage', 'v1', credentials=self.credentials)

    def _list_enabled_services(self):
        parent = '/'.join(['projects', self.project_id])
        request = self.service_usage_service.services().list(
            parent=parent, filter='state:ENABLED')
        response = request.execute()
        return [service['config']['name'] for service in response['services']]

    @contextlib.contextmanager
    def disable_services(self, services):
        try:
            yield
        finally:
            for service in services:
                service_name = '/'.join(
                    ['projects', self.project_id, 'services', service['name']])
                request = self.service_usage_service.services().disable(
                    name=service_name, body={'disableDependentServices': False})
                request.execute()

    def test_enable_services(self):
        with self.disable_services(self.SERVICES):
            self.enable_service_workflow.enable_required_services(
                project_id=self.project_id, services=self.SERVICES)
            enabled_services = self._list_enabled_services()
            for service in self.SERVICES:
                self.assertIn(service['name'], enabled_services)


class ServiceAccountKeyGenerationWorkflowIntegrationTest(test_base.BaseTest):
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
        self.iam_service = discovery.build(
            'iam', 'v1', credentials=self.credentials)
        self.cloudresourcemanager_service = discovery.build(
            'cloudresourcemanager', 'v1', credentials=self.credentials)

    def _list_service_accounts(self):
        resource_name = '/'.join(['projects', self.project_id])
        request = self.iam_service.projects().serviceAccounts().list(
            name=resource_name)
        response = request.execute()
        return [account['email'] for account in response['accounts']]

    def _get_iam_policy(self):
        request = self.cloudresourcemanager_service.projects().getIamPolicy(
            resource=self.project_id)
        return request.execute()

    @contextlib.contextmanager
    def delete_service_account(self, project_id, service_account_email):
        try:
            yield
        finally:
            resource_name = 'projects/{}/serviceAccounts/{}'.format(
                project_id, service_account_email)
            request = self.iam_service.projects().serviceAccounts().delete(
                name=resource_name)
            request.execute()

    @contextlib.contextmanager
    def reset_iam_policy(self, member, roles):
        """Remove bindings as specified by the args.

        If we only delete the service account, the role bindings for that
        service account still exist. So we need to also reset the iam policy.

        Args:
            member: str, the member to remove from the IAM policy. If should
                have the following format:
                "serviceAccount:{sa_id}@{project_id}.iam.gserviceaccount.com"
            roles: str, the role the member should be removed from. Valid roles
                can be found on
                https://cloud.google.com/iam/docs/understanding-roles

        Yields:
            Nothing
        """

        try:
            yield
        finally:
            policy = self._get_iam_policy()
            for role in roles:
                # Remove the given members for a role
                for binding in policy['bindings']:
                    if binding['role'] == role and member in binding['members']:
                        binding['members'].remove(member)
                        break

            # Remove any empty bindings.
            policy['bindings'] = [b for b in policy['bindings'] if b['members']]
            body = {'policy': policy}
            request = self.cloudresourcemanager_service.projects().setIamPolicy(
                resource=self.project_id, body=body)
            request.execute()

    def assert_valid_service_account_key(self, key_file_content):
        key = json.loads(key_file_content)
        for attributes in self.KEY_EXPECTED_ATTRIBUTES:
            self.assertIn(attributes, key)
        self.assertEqual(self.project_id, key['project_id'])
        self.assertEqual('service_account', key['type'])

    def test_create_service_account_key(self):
        service_account_id = utils.get_resource_name(resource_type='sa')
        service_account_email = '{}@{}.iam.gserviceaccount.com'.format(
            service_account_id, self.project_id)
        member = 'serviceAccount:{}'.format(service_account_email)
        with self.delete_service_account(self.project_id,
                                         service_account_email):
            with self.reset_iam_policy(member, self.ROLES):
                with tempfile.NamedTemporaryFile(mode='w+t') as key_file:
                    self.service_account_workflow.create_key(
                        self.project_id, service_account_id,
                        'Test Service Account', self.ROLES, key_file.name)
                    self.assert_valid_service_account_key(key_file.file.read())

                    # Assert the service account is created
                    all_service_accounts = self._list_service_accounts()
                    self.assertIn(service_account_email, all_service_accounts)

                    # Assert the service account has correct roles
                    policy = self._get_iam_policy()
                    for role in self.ROLES:
                        find_role = False
                        for binding in policy['bindings']:
                            if binding['role'] == role:
                                find_role = True
                                self.assertIn(member, binding['members'])
                        self.assertTrue(find_role)


class DeploygkeWorkflowIntegrationTest(test_base.DjangoFileGeneratorTest):
    """Integration test for django_cloud_deploy.workflow._deploygke."""

    def setUp(self):
        super().setUp()
        self.container_service = discovery.build(
            'container', 'v1', credentials=self.credentials)
        self.deploygke_workflow = (_deploygke.DeploygkeWorkflow(
            self.credentials))

    @contextlib.contextmanager
    def clean_up_cluster(self, cluster_name):
        try:
            yield
        finally:
            request = self.container_service.projects().zones().clusters(
            ).delete(
                projectId=self.project_id,
                zone=self.zone,
                clusterId=cluster_name)
            request.execute()

    @contextlib.contextmanager
    def clean_up_docker_image(self, image_name):
        try:
            yield
        finally:
            # TODO: Rewrite this subprocess call with library call.
            subprocess.check_call(
                ['gcloud', 'container', 'images', 'delete', image_name, '-q'])

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
                admin_url = self.deploygke_workflow.deploy_new_app_sync(
                    project_id=self.project_id,
                    cluster_name=cluster_name,
                    app_directory=self.project_dir,
                    app_name=self.project_name,
                    image_name=self.image_tag,
                    secrets=secrets)
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
                project_name, project_id,
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
            self.project_name, self.project_id,
            project_creation=_project.CreationMode.CREATE_IF_NEEDED)
        output = subprocess.check_output(
            ['gcloud', 'config', 'list', 'project',
             '--format=csv(core.project)'], universal_newlines=True)
        self.assertIn(self.project_id, output)


class StaticContentServeWorkflowIntegrationTest(
        test_base.DjangoFileGeneratorTest):
    """Integration test for django_gke.workflow._static_content_serve."""

    def setUp(self):
        super().setUp()
        self._static_content_serve_workflow = (
            _static_content_serve.StaticContentServeWorkflow(self.credentials))
        self._storage_service = discovery.build(
            'storage', 'v1', credentials=self.credentials)

    def _delete_objects(self, bucket_name):
        request = self._storage_service.objects().list(bucket=bucket_name)
        response = request.execute()
        object_names = [item['name'] for item in response['items']]
        for object_name in object_names:
            request = self._storage_service.objects().delete(
                bucket=bucket_name, object=object_name)
            request.execute()

    @contextlib.contextmanager
    def clean_up_bucket(self, bucket_name):
        try:
            yield
        finally:
            self._delete_objects(bucket_name)
            request = self._storage_service.buckets().delete(bucket=bucket_name)
            request.execute()

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


class DatabaseWorkflowIntegrationTest(test_base.DjangoFileGeneratorTest):
    """Integration test for django_cloud_deploy.workflow._database."""

    def setUp(self):
        super().setUp()
        self.database_workflow = _database.DatabaseWorkflow(self.credentials)
        self.sqladmin_service = discovery.build(
            'sqladmin',
            'v1beta4',
            cache_discovery=False,
            credentials=self.credentials)

    @contextlib.contextmanager
    def clean_up_sql_instance(self, instance_name):
        try:
            yield
        finally:
            request = self.sqladmin_service.instances().delete(
                instance=instance_name, project=self.project_id)
            request.execute()

    @contextlib.contextmanager
    def clean_up_database(self, instance_name, database_name):
        try:
            yield
        finally:
            request = self.sqladmin_service.databases().delete(
                database=database_name,
                instance=instance_name,
                project=self.project_id)
            request.execute()

    def _list_instances(self):
        request = self.sqladmin_service.instances().list(
            project=self.project_id)
        response = request.execute()
        instances = [item['name'] for item in response['items']]
        return instances

    def _list_databases(self, instance_name):
        request = self.sqladmin_service.databases().list(
            project=self.project_id, instance=instance_name)
        response = request.execute()
        databases = [item['name'] for item in response['items']]
        return databases

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
                    project_id=self.project_id,
                    instance_name=self.instance_name,
                    database_name=self.database_name,
                    database_password=self.database_password,
                    superuser_name=superuser_name,
                    superuser_email=superuser_email,
                    superuser_password=superuser_password)

                # Assert Cloud SQL instance is created
                instances = self._list_instances()
                self.assertIn(self.instance_name, instances)

                # Assert database is created
                databases = self._list_databases(self.instance_name)
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
