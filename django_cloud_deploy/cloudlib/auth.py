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
import shutil
import subprocess
from typing import Optional

from google.oauth2 import credentials


class AuthClient(object):
    """A class for GCP authentication."""

    @staticmethod
    def create_default_credentials() -> credentials.Credentials:
        """Retrieves google application default credentials for authentication.

        Uses subprocess to call gcloud auth application-default login. User must
        have gcloud installed.

        Returns:
            Credentials Object
        """

        # We can not use "gcloud auth application-default login" here because
        # we use "gcloud app deploy" to deploy a Django app to app-engine. It
        # requires "gcloud auth login".
        command = ['gcloud', 'auth', 'login', '-q']
        subprocess.check_call(command,
                              stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL)

        return AuthClient.get_default_credentials()

    @staticmethod
    def get_default_credentials() -> Optional[credentials.Credentials]:
        """Get the default credentials object created by "gcloud auth login".

        Returns:
            The credentials object if it is valid and not expired. Otherwise
            None.
        """
        credentials_path = AuthClient._get_active_account_adc_path()
        try:
            creds = credentials.Credentials.from_authorized_user_file(
                credentials_path)
            if creds.expired:
                return None
            else:
                return creds

        # If credentials file not found or it is invalid.
        except (AttributeError, ValueError, FileNotFoundError):
            return None

    @staticmethod
    def get_active_account() -> str:
        """Get the active account logged in on gcloud."""
        gcloud_path = shutil.which('gcloud')
        assert gcloud_path, 'gcloud could not be found'

        command = [gcloud_path, 'info', '--format=value(config.account)']
        return subprocess.check_output(command,
                                       universal_newlines=True).rstrip()

    @staticmethod
    def _get_active_account_adc_path() -> str:
        """Get application default credentials path of the given account.

        After we run "gcloud auth login", a credentials file for the login
        account is created under
        "~/.config/gcloud/legacy_credentials/<account>/adc.json". The accesses
        given by "gcloud auth login" is a superset of
        "gcloud auth application-default login".

        Returns:
            Absolute path of the application default credentials path of the
            given account.
        """
        gcloud_path = shutil.which('gcloud')
        assert gcloud_path, 'gcloud could not be found'

        command = [
            gcloud_path, 'info',
            '--format=value(config.paths.global_config_dir)'
        ]
        gcloud_config_path = subprocess.check_output(
            command, universal_newlines=True).rstrip()
        active_account = AuthClient.get_active_account()
        # These hardcoded values are also hardcoded by gcloud.
        return os.path.join(gcloud_config_path, 'legacy_credentials',
                            active_account, 'adc.json')
