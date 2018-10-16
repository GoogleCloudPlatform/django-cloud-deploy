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

import contextlib

from googleapiclient import discovery

from django_cloud_deploy.cloudlib import database
from django_cloud_deploy.integration_tests.lib import test_base
from django_cloud_deploy.integration_tests.lib import utils


class DatabaseClientIntegrationTest(test_base.BaseTest):

    def setUp(self):
        super().setUp()
        self.database_client = database.DatabaseClient.from_credentials(
            self.credentials)
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

    def test_create_instance(self):
        instance_name = utils.get_resource_name(resource_type='sql-instance')
        with self.clean_up_sql_instance(instance_name):
            self.database_client.create_instance_sync(self.project_id,
                                                      instance_name)
            instances = self._list_instances()
            self.assertIn(instance_name, instances)

    def test_create_database(self):
        instance_name = utils.get_resource_name(resource_type='sql-instance')
        database_name = utils.get_resource_name(resource_type='db')
        with self.clean_up_sql_instance(instance_name):
            with self.clean_up_database(instance_name, database_name):
                self.database_client.create_instance_sync(
                    self.project_id, instance_name)
                self.database_client.create_database_sync(
                    self.project_id, instance_name, database_name)
                databases = self._list_databases(instance_name)
                self.assertIn(database_name, databases)
