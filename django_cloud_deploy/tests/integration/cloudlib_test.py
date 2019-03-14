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

from django_cloud_deploy.cloudlib import container
from django_cloud_deploy.cloudlib import database
from django_cloud_deploy.cloudlib import service_account
from django_cloud_deploy.cloudlib import static_content_serve
from django_cloud_deploy.tests.lib import test_base
from django_cloud_deploy.tests.lib import utils


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
