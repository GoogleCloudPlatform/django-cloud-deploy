# Copyright 2019 Google LLC
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
"""Automatic deletion of resources more than 2 hours old on GCP."""

import datetime
import re

from django_cloud_deploy.tests.lib import test_base
from django_cloud_deploy.tests.lib import utils
from googleapiclient import discovery
from googleapiclient import errors


class GCPResourceCleanUp(test_base.ResourceCleanUp, test_base.ResourceList):
    """Clean up GCP resources more than 2 hours old."""

    MAX_DIFF = datetime.timedelta(hours=2)

    def _should_delete(self, resource_name: str) -> bool:
        """Return whether the given resource should be deleted.

        If a resource is not more than 2 hours old, we should not delete it
        because these resources are still being used by other test runs.
        Also, the GCP project we are using for test already contains some
        resources. For example, service accounts for authentication. Those
        resources should not be deleted.

        Args:
            resource_name: Name of the resource we want to check whether it
                should be deleted. The resource created for testing should be
                in format similar with "db-20190307223549-b4wl".
                There are other resources that we do not want to clean up.
                Some special examples are
                "project20190308221801exjk-instance", sql instance name in e2e
                tests.
                "project20190308221801exjk", cluster name in e2e tests

        Returns:
            Whether this resource should be deleted.
        """
        if not re.match(r'[a-z\-]+\-?[0-9]{14}\-?[a-z0-9]+', resource_name):
            return False
        now = datetime.datetime.utcnow()
        create_time = utils.parse_creation_time(resource_name)
        diff = now - create_time
        return diff > self.MAX_DIFF

    def delete_expired_clusters(self):
        container_service = discovery.build('container',
                                            'v1',
                                            credentials=self.credentials,
                                            cache_discovery=False)
        for cluster_name in self.list_clusters(container_service):
            if self._should_delete(cluster_name):
                self._delete_cluster(cluster_name, container_service)

    def delete_expired_buckets(self):
        storage_service = discovery.build('storage',
                                          'v1',
                                          credentials=self.credentials,
                                          cache_discovery=False)
        for bucket_name in self.list_buckets(storage_service):
            if self._should_delete(bucket_name):
                self._delete_bucket(bucket_name, storage_service)

    def delete_expired_sql_instances(self):
        sqladmin_service = discovery.build('sqladmin',
                                           'v1beta4',
                                           credentials=self.credentials,
                                           cache_discovery=False)
        for instance_name in self.list_instances(sqladmin_service):
            if self._should_delete(instance_name):
                self._clean_up_sql_instance(instance_name, sqladmin_service)

    def delete_expired_service_accounts(self):
        iam_service = discovery.build('iam',
                                      'v1',
                                      credentials=self.credentials,
                                      cache_discovery=False)
        for account_email in self.list_service_accounts(iam_service):
            account_name = account_email.split('@')[0]
            if self._should_delete(account_name):
                self._delete_service_account(account_email, iam_service)

    def reset_expired_iam_policy(self):
        cloudresourcemanager_service = discovery.build(
            'cloudresourcemanager',
            'v1',
            credentials=self.credentials,
            cache_discovery=False)
        request = cloudresourcemanager_service.projects().getIamPolicy(
            resource=self.project_id)
        policy = request.execute()
        for binding in policy['bindings']:
            for member in binding['members']:
                # Member should look like the follows:
                # serviceAccount:sa-20190301000243-bu47@aaa.com
                service_account_name = member.split('@')[0].split(':')[-1]
                if self._should_delete(service_account_name):
                    binding['members'].remove(member)

        policy['bindings'] = [b for b in policy['bindings'] if b['members']]
        body = {'policy': policy}
        request = cloudresourcemanager_service.projects().setIamPolicy(
            resource=self.project_id, body=body)
        try:
            request.execute()
        except errors.HttpError:
            # This might fail due to concurrent iam policy changes.
            # In resource cleaning, we do not care whether this run succeed or
            # not. If it fails one time due to concurrent changes, it will
            # succeed later when concurrent changes do not exist.
            pass

    def test_dummy(self):
        """This is not a test, but cleans up test related resources.

        It is prefixed with "test" because we are using pytest to automatically
        run this function. If it does not start with "test", then pytest will
        ignore the function.
        """
        self.delete_expired_clusters()
        self.delete_expired_buckets()
        self.delete_expired_sql_instances()
        self.delete_expired_service_accounts()
        self.reset_expired_iam_policy()
