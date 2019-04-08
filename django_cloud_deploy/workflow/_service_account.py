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
"""Workflow for creating service accounts and generating keys."""

import json
import os
from typing import Any, Dict, List

from django_cloud_deploy.cloudlib import service_account

from google.auth import credentials


class ServiceAccountKeyGenerationWorkflow(object):
    """A class to control the generation of service account keys."""

    def __init__(self, credentials: credentials.Credentials):
        self._service_account_client = (
            service_account.ServiceAccountClient.from_credentials(credentials))

    def create_service_account_and_key(self, project_id: str,
                                       service_account_id: str,
                                       service_account_name: str,
                                       roles: List[str]) -> str:
        """Aggregate function to create service accounts and get their keys.

        Args:
            project_id: GCP project id you want to create this service account.
            service_account_id: Id of your service account. For example, a
                service account should be in the following format:
                <service_account_id>@<project_id>.iam.gserviceaccount.com
            service_account_name: Display name of your service account.
            roles: Roles the service account should have. Valid roles can be
                found on https://cloud.google.com/iam/docs/understanding-roles

        Returns:
            The service account key content. Should like the following:
                {
                    "type": "service_account",
                    "project_id": "...",
                    "private_key_id": "...",
                    "private_key": "..."
                    "client_email": "...",
                    "client_id": "...",
                    "auth_uri": "...",
                    "token_uri": "...",
                    "auth_provider_x509_cert_url": "...",
                    "client_x509_cert_url": "..."
                }
        """

        self._service_account_client.create_service_account(
            project_id, service_account_id, service_account_name, roles)
        key_data = self._service_account_client.create_key(
            project_id, service_account_id)
        return key_data

    @staticmethod
    def load_service_accounts() -> List[Dict[str, Any]]:
        """Load information of the service accounts to create from a json file.

        Returns:
            service_accounts: A list of the service accounts to be created.
        """

        data_dir = os.path.join(os.path.dirname(__file__), 'data')
        data_file_path = os.path.join(data_dir, 'service_accounts.json')
        with open(data_file_path) as data_file:
            service_accounts = json.load(data_file)
        return service_accounts
