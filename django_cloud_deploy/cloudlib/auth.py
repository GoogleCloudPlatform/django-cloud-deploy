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

import subprocess

import google.auth
from google.auth import credentials

from django_cloud_deploy.utils import base_client


class AuthClient(base_client.BaseClient):
    """A class for GCP authentication."""

    def gcloud_login(self):
        """Sets the user account in the Gcloud CLI.

    Uses subprocess call to gcloud auth login. This is needed as the user
    must have the current account active via the Gcloud CLI.

    """
        command = ['gcloud', 'auth', 'login', '-q']
        subprocess.check_call(command, stdout=self._stdout, stderr=self._stderr)

    def create_default_credentials(self) -> credentials.Credentials:
        """Retrieves google application default credentials for authentication.

    Uses subprocess to call gcloud auth application-default login. User must
    have gcloud installed.

    Returns:
      Credentials Object

    """
        command = ['gcloud', 'auth', 'application-default', 'login', '-q']
        subprocess.check_call(command, stdout=self._stdout, stderr=self._stderr)
        creds, _ = google.auth.default()
        return creds

    def authenticate_docker(self):
        """To authenticate to Container Registry we use gcloud to help Docker.

    See:
     https://cloud.google.com/container-registry/docs/advanced-authentication

    """
        command = ['gcloud', 'auth', 'configure-docker', '-q']
        subprocess.check_call(command, stdout=self._stdout, stderr=self._stderr)
