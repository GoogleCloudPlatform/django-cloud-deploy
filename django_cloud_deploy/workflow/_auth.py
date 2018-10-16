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

from google.auth import credentials

from django_cloud_deploy.cloudlib import auth


class AuthWorkflow(object):
    """A class to control the workflow for authenticate GCP."""

    def __init__(self, auth_client: auth.AuthClient):
        self._auth_client = auth_client

    def get_credentials(self) -> credentials.Credentials:
        self._auth_client.gcloud_login()

        # Enable Docker to work with the Project
        self._auth_client.authenticate_docker()
        return self._auth_client.create_default_credentials()
