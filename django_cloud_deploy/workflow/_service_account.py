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

KEY_PATH_TEMPLATE = '{}/{}.json'


class ServiceAccount(object):
    """ Service Accounts for permissions in Google Cloud.

    Attributes:
        id_: Id of your service account. For example, a
            service account should be in the following format:
            <service_account_id>@<project_id>.iam.gserviceaccount.com
        name: Display name of your service account.
        file_name: Name of the secrets file.
        roles: Roles the service account should have. Valid roles can be
            found on https://cloud.google.com/iam/docs/understanding-roles
        key_path: The path to store your key.
    """
    def __init__(self, id_: str, name: str, file_name: str, roles: List[str],
                 key_path: str = None):
        """ Create a service account.

        Args:
            id_: Id of your service account. For example, a
                service account should be in the following format:
                <service_account_id>@<project_id>.iam.gserviceaccount.com
            name: Display name of your service account.
            file_name: Name of the secrets file.
            roles: Roles the service account should have. Valid roles can be
                found on https://cloud.google.com/iam/docs/understanding-roles
            key_path: The path to store your key.

        Returns:
            service_account: ServiceAccount
        """
        self.id_ = id_
        self.name = name
        self.file_name = file_name
        self.roles = roles
        if key_path is None:
            key_path = KEY_PATH_TEMPLATE.format(os.path.expanduser('~'), id_)

        self.key_path = key_path


class ServiceAccountKeyGenerationWorkflow(object):
    """A class to control the generation of service account keys."""

    def __init__(self, credentials: credentials.Credentials):
        self._service_account_client = (
            service_account.ServiceAccountClient.from_credentials(credentials))

    def handle_service_accounts(
            self, project_id: str,
            database_username: str, database_password: str,
            service_accounts: List[ServiceAccount] = None) -> Dict[str, Any]:
        """Aggregate function to create service accounts and get their keys.

        First creates the service accounts on GCP.
        It then downloads the keys to the local machine.
        Finally it generates the secrets that will be used for kubernetes.

        Args:
            project_id: GCP Project Id.
            database_username: Name of the database user.
            database_password: Password of the database.
            service_accounts: List of service accounts to create.

        Returns:
            secrets: The dictionary used for kubernetes to set up secrets.
        """

        service_accounts = (
            self.
            create_service_accounts_and_keys(project_id, service_accounts))

        # Prepare Kubernetes secret object based on service account keys.
        secrets = self.generate_base_secrets(
            database_username, database_password
        )
        return self.generate_service_account_secrets(
            service_accounts, secrets
        )

    def create_service_accounts_and_keys(
            self, project_id: str,
            service_accounts: List[ServiceAccount] = None
            ) -> Dict[str, ServiceAccount]:
        """Loads service account from json file and creates them.

        Args:
            project_id: GCP Project Id.
            service_accounts: List of service accounts to create.

        Returns:
            service_account_keys: New service accounts with key data.
        """
        service_accounts = service_accounts or self.load_service_accounts()

        service_account_keys = {}
        for s_a in service_accounts:
            service_account_keys[s_a.id_] = s_a
            self.create_key(project_id, s_a)

        return service_account_keys

    def create_key(self, project_id: str, service_account_obj: ServiceAccount):
        """Creates the service accounts and retrieves the key for the project.

        Args:
            project_id: The GCP project id to create service accounts.
            service_account_obj: The service account to create and retrieve key.
        """

        self._service_account_client.create_service_account(
            project_id,
            service_account_obj.id_,
            service_account_obj.name,
            service_account_obj.roles)
        key_data = self._service_account_client.create_key(
            project_id, service_account_obj.id_)
        with open(service_account_obj.key_path, 'w') as output_file:
            output_file.write(json.dumps(key_data, sort_keys=True))

    @staticmethod
    def generate_service_account_secrets(
            service_accounts: Dict[str, ServiceAccount],
            secrets: Dict[str, Any] = None) -> Dict[str, Any]:
        """Generates the secrets used by kubernetes.

        Args:
            service_accounts: Service Accounts keyed by their id_.
            secrets: Initial secrets that don't come from service accounts.
        Returns:
            secrets: Secret data use by kubernetes.
        """
        if not secrets:
            secrets = {}

        for s_a_id, s_a in service_accounts.items():
            with open(s_a.key_path) as key_file:
                key_content = key_file.read()

            secrets[s_a_id] = {
                s_a.file_name: key_content
            }

        return secrets

    @staticmethod
    def load_service_accounts() -> List[ServiceAccount]:
        """Load information of the service accounts to create from a json file.

        Returns:
            service_accounts: A list of the service accounts to be created.
        """

        data_dir = os.path.join(os.path.dirname(__file__), 'data')
        data_file_path = os.path.join(data_dir, 'service_accounts.json')
        with open(data_file_path) as data_file:
            service_accounts = [ServiceAccount(**d)
                                for d in json.load(data_file)]
        return service_accounts

    @staticmethod
    def generate_base_secrets(database_username: str,
                              database_password: str):
        """Generates base secrets not related to service accounts.

        Args:
            database_username: Name of the database user.
            database_password: Password of the database.

        Returns:
            secrets: Base secret data use by kubernetes.
        """
        return {
            'cloudsql': {
                'username': database_username,
                'password': database_password
            }
        }
