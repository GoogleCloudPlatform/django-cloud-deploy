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
"""Manages user's Google Cloud Platform billing setup."""

from typing import Any, Dict, List

from googleapiclient import discovery
from google.auth import credentials


class BillingError(Exception):
    pass


class BillingClient(object):
    """A class for managing Google Cloud Platform projects billing setup."""

    def __init__(self, billing_service: discovery.Resource):
        self._billing_service = billing_service

    @classmethod
    def from_credentials(cls, credentials: credentials.Credentials):
        return cls(
            discovery.build('cloudbilling',
                            'v1',
                            credentials=credentials,
                            cache_discovery=False))

    def check_billing_enabled(self, project_id: str) -> bool:
        """Check is billing enabled for the given project.

        Args:
            project_id: GCP project id.

        Returns:
            Is billing enabled for the given project.
        """
        return (self.get_billing_account(project_id).get(
            'billingEnabled', False))

    def get_billing_account(self, project_id: str) -> Dict[str, Any]:
        """Gets the billing information for the given project.

        Args:
            project_id: GCP project id.

        Returns:
            The billing information used by the project.

            Example:
                {
                     'name': "projects/project-abc/billingInfo",
                     'projectId': "project-abc",
                     'billingAccountName': "billingAccounts/01D3-2564D9-F29D2E",
                     'billingEnabled': true
                }
        """
        project_name = 'projects/{}'.format(project_id)
        request = self._billing_service.projects().getBillingInfo(
            name=project_name)
        response = request.execute(num_retries=5)
        return response

    def list_billing_accounts(self, only_open_accounts: bool = False
                             ) -> List[Dict[str, Any]]:
        """List billing accounts the user has.

        Args:
            only_open_accounts: List only opened billing accounts or including
                closed billing accounts. Associating a project with a closed
                billing account has the same effect as disabling billing on that
                project.

        Raises:
            BillingError: If failed to list user's billing accounts.

        Returns:
            A list of all billing accounts the user has. The result should look
            like the following:
                [
                    {
                        'name': 'billingAccounts/1',
                        'displayName': 'Fake Account 1',
                        'open': True
                    },
                    {
                        'name': 'billingAccounts/2',
                        'displayName': 'Fake Account 2',
                        'open': False
                    },
                ]
        """
        request = self._billing_service.billingAccounts().list()
        all_billing_accounts = []
        while True:
            response = request.execute(num_retries=5)
            all_billing_accounts += response.get('billingAccounts', [])
            if 'nextPageToken' in response:
                request = self._billing_service.billingAccounts().list(
                    pageToken=response['nextPageToken'])
            else:
                break
        if only_open_accounts:
            return [
                account for account in all_billing_accounts
                if account.get('open', False)
            ]
        else:
            return all_billing_accounts

    def enable_project_billing(self, project_id: str,
                               billing_account_name: str):
        """Enable billing for the given project.

        Args:
            project_id: GCP project id.
            billing_account_name: Name of the billing account the given project
                should use. It should look like "billingAccounts/1"

        Raises:
            BillingError: If failed to update project billing info.
        """
        project_name = 'projects/{}'.format(project_id)
        body = {
            'billingAccountName': billing_account_name,
        }
        request = self._billing_service.projects().updateBillingInfo(
            name=project_name, body=body)
        response = request.execute(num_retries=5)

        if 'billingEnabled' not in response:
            raise BillingError(
                'Unexpected response setting project "{}" with billing account '
                '"{}"'.format(project_id, billing_account_name))
