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
"""Manages Google Cloud Platform service accounts and iam policies.

See
https://cloud.google.com/iam/reference/rest/
https://cloud.google.com/resource-manager/reference/rest/
"""

import base64
from typing import Any, Dict, List

import backoff
from googleapiclient import discovery
from googleapiclient import errors

from google.auth import credentials


def _not_conflict_code(error: errors.HttpError) -> bool:
    return error.resp.status != 409


class ServiceAccountCreationError(Exception):
    pass


class ServiceAccountKeyCreationError(Exception):
    pass


class ServiceAccountClient(object):
    """Help with creation and generation of service account keys."""

    def __init__(self, iam_service: discovery.Resource,
                 cloudresourcemanager_service: discovery.Resource):
        self._iam_service = iam_service
        self._cloudresourcemanager_service = cloudresourcemanager_service

    @classmethod
    def from_credentials(cls, credentials: credentials.Credentials):
        return cls(
            discovery.build('iam',
                            'v1',
                            credentials=credentials,
                            cache_discovery=False),
            discovery.build('cloudresourcemanager',
                            'v1',
                            credentials=credentials,
                            cache_discovery=False))

    def _get_iam_policy(self, project_id):
        request = self._cloudresourcemanager_service.projects().getIamPolicy(
            resource=project_id)
        response = request.execute(num_retries=5)
        if 'bindings' not in response:
            raise ServiceAccountCreationError(
                ('unexpected response getting iam policy of project "{}":{}'.
                 format(project_id, response)))

        return response

    def _generate_updated_iam_policy(self, policy, member: str, role: str):
        """Generate a new bindings object after updating iam policy."""

        # Avoid changing the input policy.
        policy = dict(policy)

        # The given member might already have the provided role
        for binding in policy['bindings']:
            if binding['role'] == role:
                if member not in binding['members']:
                    binding['members'].append(member)
                return policy

        new_bindings = {
            'members': [member],
            'role': role,
        }
        policy['bindings'].append(new_bindings)
        return policy

    @backoff.on_exception(backoff.expo,
                          errors.HttpError,
                          max_tries=5,
                          giveup=_not_conflict_code)
    def _update_iam_policy_with_retry(self, project_id: str, member: str,
                                      roles: List[str]) -> Dict[str, Any]:
        """Try updating iam policy for at most 5 times.

        This function is used when changing iam policy. Most likely
        errors.HttpError with error code 409 happens when concurrent changes are
        made to iam policy change. We might be able to make this iam change when
        trying again. When giveup event happens, the exception is reraised.

        Args:
            project_id: GCP project id.
            member: Identifier for a service account in the following format:
                'serviceAccount:<service_account_id>@<project_id>.iam.gserviceaccount.com'
            roles: Roles the service account should have. Valid roles can be
                found on https://cloud.google.com/iam/docs/understanding-roles

        Returns:
            A valid iam policy object.
        """

        policy = self._get_iam_policy(project_id)
        for role in roles:
            policy = self._generate_updated_iam_policy(policy, member, role)

        body = {'policy': policy}
        request = self._cloudresourcemanager_service.projects().setIamPolicy(
            resource=project_id, body=body)

        return request.execute(num_retries=5)

    def create_service_account(self, project_id: str, service_account_id: str,
                               service_account_name: str, roles: List[str]):
        """Create a service account and assign it with the given roles.

        Args:
            project_id: GCP project id.
            service_account_id: Id of your service account. For example, a
                service account should be in the following format:
                <service_account_id>@<project_id>.iam.gserviceaccount.com
            service_account_name: Display name of your service account.
            roles: Roles the service account should have. Valid roles can be
                found on https://cloud.google.com/iam/docs/understanding-roles

        Raises:
            ServiceAccountCreationError: When it fails to create a service
                account.
        """

        # Create a service account without any roles
        resource_name = '/'.join(['projects', project_id])
        body = {
            'accountId': service_account_id,
            'serviceAccount': {
                'displayName': service_account_name,
            }
        }
        request = self._iam_service.projects().serviceAccounts().create(
            name=resource_name, body=body)
        try:
            response = request.execute(num_retries=5)
            # When the api call succeed, the response is a Service Account
            # object. See
            # https://cloud.google.com/iam/reference/rest/v1/projects.serviceAccounts/create
            if 'name' not in response:
                raise ServiceAccountCreationError(
                    'unexpected response creating service account "{}": {}'.
                    format(service_account_id, response))
        except errors.HttpError as e:
            if e.resp.status == 409:
                # Most likely our tool has created the service account already
                # and is being re-run. This error code is fine as we just need
                # the service accounts to exist. Later on we assign the
                # appropriate roles for each one.
                pass
            if e.resp.status == 400:
                raise ServiceAccountCreationError(
                    'Service account id {} is invalid'.format(
                        service_account_id))

        # Bind the newly created service account with given roles
        member = ('serviceAccount:{}@{}.iam.gserviceaccount.com'.format(
            service_account_id, project_id))
        response = self._update_iam_policy_with_retry(project_id, member, roles)

        # When the api call succeed, the response is a Policy object.
        # See
        # https://cloud.google.com/resource-manager/reference/rest/v1/projects/setIamPolicy
        if 'bindings' not in response:
            raise ServiceAccountCreationError(
                ('unexpected response granting roles to service account "{}":{}'
                 .format(service_account_id, response)))

    def create_key(self, project_id: str, service_account_id: str) -> str:
        """Create a new key of the given service account.

        Args:
            project_id: GCP project id.
            service_account_id: Id of your service account. For example, a
                service account should be in the following format:
                <service_account_id>@<project_id>.iam.gserviceaccount.com

        Raises:
            ServiceAccountKeyCreationError: When it fails to create a service
                account key.

        Returns:
            Service account file content in the following format:
                "{
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
                }"
        """

        service_account_email = ('{}@{}.iam.gserviceaccount.com'.format(
            service_account_id, project_id))
        resource_name = '/'.join(
            ['projects', project_id, 'serviceAccounts', service_account_email])
        body = {
            'privateKeyType': 'TYPE_GOOGLE_CREDENTIALS_FILE',
            'keyAlgorithm': 'KEY_ALG_RSA_2048',
        }

        request = self._iam_service.projects().serviceAccounts().keys().create(
            name=resource_name, body=body)
        try:
            response = request.execute(num_retries=5)
        except errors.HttpError as e:
            if e.resp.status == 400:
                raise ServiceAccountKeyCreationError(
                    'Invalid service account email "{}" or project id "{}"'.
                    format(service_account_email, project_id))
        # When the api call succeed, the response is a Service Account Key
        # object. See
        # https://cloud.google.com/iam/reference/rest/v1/projects.serviceAccounts.keys#ServiceAccountKey
        if 'privateKeyData' not in response:
            raise ServiceAccountKeyCreationError(
                ('unexpected response creating service account key "{}": {}'.
                 format(service_account_id, response)))
        return base64.standard_b64decode(
            response['privateKeyData']).decode('utf-8')
