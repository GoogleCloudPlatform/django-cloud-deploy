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

import os
import subprocess

from django_cloud_deploy.utils import base_client


class ServiceAccountClient(base_client.BaseClient):
    """Help with creation and generation of service account keys."""

    def __init__(self, project_id, project_name, debug=False):
        super().__init__(debug)
        self._project_id = project_id
        self._project_name = project_name

    def create_service_account_workflow(self):
        """Create a service account with necessary roles and download keys.

    Prerequisite: gcloud is configured with the correct user and project.
    Returns:
      key_path: str, the service account key path in your local file system.
    """
        self._create_service_account()
        self._grant_roles()
        return self._download_keys()

    def _create_service_account(self, service_account_name=None):
        """Create a service account.

    This function just creates the service account but does not grant any roles
    to this account.

    Args:
      service_account_name: str, this is used in test to create a service
                            account with name different with default.
    """
        service_account_name = (service_account_name or
                                'cloudsql-oauth-credentials')
        subprocess.check_call([
            'gcloud', 'iam', 'service-accounts', 'create', service_account_name,
            '--display-name', service_account_name
        ],
                              stdout=self._stdout,
                              stderr=self._stderr)

    def _grant_roles(self, service_account_name=None):
        """Grant the service account with roles to access cloud sql.

    This function will give the service account the following roles:
      1. Cloud SQL Client
      2. Cloud SQL Editor
      3. Cloud SQL Admin

    Args:
      service_account_name: str, this is used in test to create a service
                            account with name different with default.
    """
        service_account_name = (service_account_name or
                                'cloudsql-oauth-credentials')
        service_account_id = '{}@{}.iam.gserviceaccount.com'.format(
            service_account_name, self._project_id)
        roles = [
            'roles/cloudsql.client', 'roles/cloudsql.editor',
            'roles/cloudsql.admin'
        ]
        for role in roles:
            subprocess.check_call([
                'gcloud', 'projects', 'add-iam-policy-binding',
                self._project_id, '--member',
                'serviceAccount:' + service_account_id, '--role', role
            ],
                                  stdout=self._stdout,
                                  stderr=self._stderr)

    def _download_keys(self, service_account_name=None):
        """Create new service account key and download it.

    This key will be used by the cloudsql-proxy container to get access to
    cloud sql instance.

    Args:
      service_account_name: str, this is used in test to create a service
                            account with name different with default.
    Returns:
      key_path: str, the service account key path in your local file system.
    """
        service_account_name = (service_account_name or
                                'cloudsql-oauth-credentials')
        service_account_id = '{}@{}.iam.gserviceaccount.com'.format(
            service_account_name, self._project_id)
        home_dir = os.path.expanduser('~')
        key_path = '{}/{}.json'.format(home_dir, service_account_id)
        subprocess.check_call([
            'gcloud', 'iam', 'service-accounts', 'keys', 'create', key_path,
            '--iam-account', service_account_id
        ],
                              stdout=self._stdout,
                              stderr=self._stderr)
        return key_path
