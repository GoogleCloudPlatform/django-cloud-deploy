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
import subprocess
import tempfile

import requests

from django_cloud_deploy.cloudlib import enable_service
from django_cloud_deploy.integration_tests.lib import test_base
from django_cloud_deploy.integration_tests.lib import utils
from django_cloud_deploy.workflow import _deploygke
from django_cloud_deploy.workflow import _enable_service
from django_cloud_deploy.workflow import _service_account
from googleapiclient import discovery


class EnableServiceWorkflowIntegrationTest(test_base.BaseTest):
    """Integration test for django_cloud_deploy.workflow._enable_service."""

    # Google drive api is not already enabled on the GCP project for integration
    # test.
    SERVICES = [{'title': 'Google Drive API', 'name': 'drive.googleapis.com'}]

    def setUp(self):
        super().setUp()
        enable_service_client = (
            enable_service.EnableServiceClient.from_credentials(
                self.credentials))
        self.enable_service_workflow = _enable_service.EnableServiceWorkflow(
            enable_service_client)
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

    If we only delete the service account, the role bindings for that service
    account still exist. So we need to also reset the iam policy.

    Args:
      member: str, the member to remove from the IAM policy. If should have
        the following format:
        "serviceAccount:{sa_id}@{project_id}.iam.gserviceaccount.com"
      roles: str, the role the member should be removed from. Valid roles can
        be found on https://cloud.google.com/iam/docs/understanding-roles

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
