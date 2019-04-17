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
"""Integration tests for module django_cloud_deploy.cloudlib."""

from django_cloud_deploy.cloudlib import cloudbuild
from django_cloud_deploy.cloudlib import cloud_source
from django_cloud_deploy.cloudlib import container
from django_cloud_deploy.cloudlib import database
from django_cloud_deploy.cloudlib import service_account
from django_cloud_deploy.cloudlib import static_content_serve
from django_cloud_deploy.tests.lib import test_base
from django_cloud_deploy.tests.lib import utils

from googleapiclient import discovery


class StaticContentServeClientIntegrationTest(test_base.DjangoFileGeneratorTest,
                                              test_base.ResourceCleanUp):
    """Integration test for django_gke.cloudlib.static_content_serve."""

    def setUp(self):
        super().setUp()
        self._static_content_serve_client = (
            static_content_serve.StaticContentServeClient.from_credentials(
                self.credentials))

    def test_reuse_bucket(self):
        bucket_name = utils.get_resource_name('bucket')
        with self.clean_up_bucket(bucket_name):
            for _ in range(3):
                self._static_content_serve_client.create_bucket(
                    self.project_id, bucket_name)

    def test_set_cors_policy(self):
        bucket_name = utils.get_resource_name('bucket')
        with self.clean_up_bucket(bucket_name):
            self._static_content_serve_client.create_bucket(
                self.project_id, bucket_name)
            url = 'http://www.example.com'
            self._static_content_serve_client.set_cors_policy(bucket_name, url)
            client = discovery.build('storage',
                                     'v1',
                                     credentials=self.credentials,
                                     cache_discovery=False)
            request = client.buckets().get(bucket=bucket_name)
            bucket_body = request.execute(num_retries=5)
            cors_policy = bucket_body.get('cors')
            self.assertNotEmpty(cors_policy)
            self.assertIn(url, cors_policy[0].get('origin'))


class ServiceAccountClientIntegrationTest(test_base.ResourceCleanUp):
    """Integration test for cloudlib.service_account."""

    _ROLES = ('roles/cloudsql.client', 'roles/cloudsql.editor',
              'roles/cloudsql.admin')

    def setUp(self):
        super().setUp()
        self._service_account_client = (
            service_account.ServiceAccountClient.from_credentials(
                self.credentials))

    def test_create_duplicate_service_account(self):
        service_account_id = utils.get_resource_name(resource_type='sa')

        # Assert no exceptions are raised when creating the same
        # service account twice
        for _ in range(2):
            self._service_account_client.create_service_account(
                self.project_id, service_account_id, 'Test Service Account',
                self._ROLES)


class DatabaseClientIntegrationTest(test_base.DjangoFileGeneratorTest,
                                    test_base.ResourceCleanUp):
    """Integration test for django_cloud_deploy.cloudlib.database."""

    def setUp(self):
        super().setUp()
        self._database_client = database.DatabaseClient.from_credentials(
            self.credentials)

    def test_reuse_cloud_sql_instance_and_database(self):
        with self.clean_up_sql_instance(self.instance_name):
            for _ in range(2):
                self._database_client.create_instance_sync(
                    self.project_id, self.instance_name)

            for _ in range(2):
                self._database_client.create_database_sync(
                    self.project_id, self.instance_name, self.database_name)


class ContainerClientIntegrationTest(test_base.ResourceCleanUp):
    """Integration test for django_cloud_deploy.cloudlib.container."""

    def setUp(self):
        super().setUp()
        self._container_client = container.ContainerClient.from_credentials(
            self.credentials)

    def test_reuse_cluster(self):
        cluster_name = utils.get_resource_name(resource_type='cluster')
        with self.clean_up_cluster(cluster_name):
            for _ in range(2):
                self._container_client.create_cluster_sync(
                    self.project_id, cluster_name)


class CloudBuildClientIntegrationTest(test_base.ResourceCleanUp,
                                      test_base.ResourceList):
    """Integration test for django_cloud_deploy.cloudlib.cloudbuild."""

    def setUp(self):
        super().setUp()
        self._cloudbuild_client = cloudbuild.CloudBuildClient.from_credentials(
            self.credentials)

    def test_create_trigger(self):
        fake_repo_name = utils.get_resource_name(resource_type='repo')
        branch_regexp = 'fake-branch'
        env_vars = {
            'MY_ENV_VAR1': utils.get_resource_name(resource_type='envvar'),
            'MY_ENV_VAR2': utils.get_resource_name(resource_type='envvar')
        }
        with self.clean_up_cloudbuild_trigger(fake_repo_name):
            self._cloudbuild_client.create_trigger(self.project_id,
                                                   fake_repo_name,
                                                   branch_regexp, env_vars)
            service = discovery.build('cloudbuild',
                                      'v1',
                                      credentials=self.credentials,
                                      cache_discovery=False)
            request = service.projects().triggers().list(
                projectId=self.project_id)
            triggers = []
            while request:
                response = request.execute()
                triggers += response.get('triggers', [])
                request = service.projects().triggers().list_next(
                    previous_request=request, previous_response=response)
            trigger_repo_names = [
                trigger.get('triggerTemplate').get('repoName')
                for trigger in triggers
            ]
            self.assertIn(fake_repo_name, trigger_repo_names)
            for trigger in triggers:
                repo_name = trigger.get('triggerTemplate').get('repoName')
                if repo_name == fake_repo_name:
                    self.assertDictEqual(env_vars, trigger.get('substitutions'))


class CloudSourceRepositoryClientIntegrationTest(test_base.ResourceCleanUp):

    def setUp(self):
        super().setUp()
        self._cloudsource_client = \
            cloud_source.CloudSourceRepositoryClient.from_credentials(
                self.credentials)
        self._cloudsource_service = \
            self._cloudsource_client._cloudsource_service

    def _create_repo(self, project_id, repo_name):
        parent = 'projects/{}'.format(project_id)
        resource_name = 'projects/{}/repos/{}'.format(project_id, repo_name)
        body = {
            'name': resource_name,
        }
        request = self._cloudsource_service.projects().repos().create(
            parent=parent, body=body)
        request.execute(num_retries=5)

    def test_list_repos(self):
        repo_name = utils.get_resource_name(resource_type='repo')
        full_repo_name = 'projects/{}/repos/{}'.format(self.project_id,
                                                       repo_name)
        prev_repos = self._cloudsource_client.list_repos(self.project_id)
        prev_repo_names = [repo.get('name') for repo in prev_repos]
        self.assertNotIn(full_repo_name, prev_repo_names)
        with self.clean_up_repo(repo_name):
            self._create_repo(self.project_id, repo_name)
            cur_repos = self._cloudsource_client.list_repos(self.project_id)
            repo_names = [repo.get('name') for repo in cur_repos]
            self.assertIn(full_repo_name, repo_names)
