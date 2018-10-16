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
from typing import List

from django_cloud_deploy.cloudlib import service_account

from google.auth import credentials


class ServiceAccountKeyGenerationWorkflow(object):
    """A class to control the generation of service account keys."""

    def __init__(self, credentials: credentials.Credentials):
        self._service_account_client = (
            service_account.ServiceAccountClient.from_credentials(credentials))

    def create_key(self, project_id: str, service_account_id: str,
                   service_account_name: str, roles: List[str],
                   output_path: str):
        """Enable required services for deploying Django apps to GKE.

    Args:
      project_id: The GCP project id to enable services.
      service_account_id: Id of your service account. For example, a service
        account should be in the following format:
          <service_account_id>@<project_id>.iam.gserviceaccount.com
      service_account_name: Display name of your service account.
      roles: Roles the service account should have. Valid roles can be found
        on https://cloud.google.com/iam/docs/understanding-roles
      output_path: The path to store your key.
    """

        self._service_account_client.create_service_account(
            project_id, service_account_id, service_account_name, roles)
        key_data = self._service_account_client.create_key(
            project_id, service_account_id)
        output_path = os.path.expanduser(output_path)
        with open(output_path, 'w') as output_file:
            output_file.write(json.dumps(key_data))
