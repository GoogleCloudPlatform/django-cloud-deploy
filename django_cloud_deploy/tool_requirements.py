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

"""Checks the user has the necesarry requirements to run the tool."""

import os
import shutil
import stat
import subprocess
import sys
import urllib.request

from typing import List

from django_cloud_deploy.cli import io


class UnableToAutomaticallyInstallError(Exception):
    """Thrown when the handle function is unable to install the requirement."""
    pass


class MissingRequirementError(Exception):
    """Thrown when a requirement is missing.

    Attributes:
        name: Name of the requirement.
        how_to_install_message: Information to help user to install
            the requirement.

    """

    def __init__(self, name: str, how_to_install_message: str):
        """Provides information on how to manually install the requirement.

        Args:
            name: Name of the requirement.
            how_to_install_message: Information to help user to install
                the requirement.
        """
        self.name = name
        self.how_to_install_message = how_to_install_message


class MissingRequirementsError(Exception):
    """Thrown when one or more requirements are missing.

    This is used by the caller to provide information to the user on how to
    manually install missing requirements.

    Attributes:
        missing_requirements: List of missing requirements.
    """

    def __init__(self, missing_requirements: List[MissingRequirementError]):
        """Initializes the MissingRequirementsError.

        Contains a list of the missing requirements with information on
        how to install all of them manually.

        Args:
            missing_requirements: List of missing requirements.
        """
        self.missing_requirements = missing_requirements


class Requirement(object):
    """Base class for all requirements the tool needs to run."""

    @classmethod
    def check(cls):
        """Checks if the requirement is installed.

        Raises:
            MissingRequirementError: If the requirement is not satisfied.
        """
        raise NotImplementedError

    @classmethod
    def handle(cls, console: io.IO):
        """Attempts to install the requirement.

        Raises:
            UnableToAutomaticallyInstall: If the installation fails.
            NotImplementedError: If we expect the user to manually install the
                requirement.
        """
        raise NotImplementedError

    @classmethod
    def check_and_handle(cls, console: io.IO):
        """Checks if requirements is installed, if not, attempts to install it.

        Checks if the requirement is installed.
        If not, attempts to install the requirement.
        If unsuccesful, provides information on how to manully install.

        Raises:
            MissingRequirementError: If the requirement needs to be
                installed manually.
        """
        try:
            cls.check()
        except MissingRequirementError as missing_requirement_error:
            try:
                cls.handle(console)
            except (NotImplementedError, UnableToAutomaticallyInstallError):
                raise missing_requirement_error


class Gcloud(Requirement):
    NAME = 'Gcloud SDK'

    @classmethod
    def check(cls):
        """Checks if Gcloud SDK is installed.

        Raises:
            MissingRequirementError: If the requirement is not found.
        """
        if not shutil.which('gcloud'):
            download_link = 'https://cloud.google.com/sdk/install'
            msg = ('Please download Google Cloud SDK'
                   'from {}'.format(download_link))
            raise MissingRequirementError(cls.NAME, msg)


class Docker(Requirement):
    NAME = 'Docker'

    @classmethod
    def check(cls):
        """Checks if Docker is installed.

        Raises:
            MissingRequirementError: If the requirement is not found.
        """
        if not shutil.which('docker'):
            download_link = 'https://store.docker.com/'
            msg = 'Please download Docker from {}'.format(download_link)
            raise MissingRequirementError(cls.NAME, msg)

        try:
            command = ['docker', 'image', 'ls']
            subprocess.check_call(command, stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError:
            # TODO: Handle for multiple OS's
            # TODO: Check output for error message given when user has
            # not ran the command
            msg = ('Docker is installed but not correctly set up.'
                   'Use the following command to fix it: '
                   'sudo usermod -a -G docker $USER\n'
                   'Then log out/log back in')
            raise MissingRequirementError(cls.NAME, msg)


class CloudSqlProxy(Requirement):
    NAME = 'Cloud Sql Proxy'

    @classmethod
    def check(cls):
        """Checks if Cloud Sql Proxy is installed.

        Raises:
            MissingRequirementError: If the requirement is not found.
        """
        if not shutil.which('cloud_sql_proxy'):
            dl_link = 'https://cloud.google.com/sql/docs/mysql/sql-proxy'
            msg = 'Please download Cloud SQL Proxy from {}'.format(dl_link)
            raise MissingRequirementError(cls.NAME, msg)

    @classmethod
    def handle(cls, console: io.IO):
        """Attempts to install the requirement.

        Raises:
            UnableToAutomaticallyInstall: If the installation fails.
            NotImplementedError: If we expect the user to manually install the
                requirement.
        """
        can_download = cls._prompt_download_requirement(console)
        if can_download:
            cls._download_cloud_sql_proxy(console)
        else:
            raise UnableToAutomaticallyInstallError

    @classmethod
    def _prompt_download_requirement(cls, console: io.IO) -> bool:
        while True:
            answer = console.ask(
                'Cloud Sql Proxy is required, download? [Y/n]:')

            if not answer or answer.strip().lower() == 'y':
                return True
            elif answer.strip().lower() == 'n':
                return False

    @classmethod
    def _download_cloud_sql_proxy(cls, console: io.IO):
        import certifi

        # We will install the proxy where gcloud is
        gcloud_path = shutil.which('gcloud')
        if gcloud_path is None:
            raise UnableToAutomaticallyInstallError

        gcloud_dir = os.path.dirname(gcloud_path)
        if sys.platform.startswith('linux'):
            url = 'https://dl.google.com/cloudsql/cloud_sql_proxy.linux.amd64'
        elif sys.platform.startswith('darwin'):
            url = 'https://dl.google.com/cloudsql/cloud_sql_proxy.darwin.amd64'
        else:
            msg = '{} is not supported, only linux/mac.'.format(sys.platform)
            raise NotImplementedError(msg)

        console.tell('Downloading Cloud Sql Proxy')

        file_name = 'cloud_sql_proxy'
        executable_name = os.path.join(gcloud_dir, file_name)
        with open(executable_name, 'wb') as file:
            with urllib.request.urlopen(url, cafile=certifi.where()) as data:
                file.write(data.read())

        st = os.stat(executable_name)
        os.chmod(executable_name, st.st_mode | stat.S_IRWXU)


_REQUIREMENTS = [
    Gcloud,
    Docker,
    CloudSqlProxy
]


def check_and_handle_requirements(console: io.IO):
    """Checks that requirements are installed. Attempts to install missing ones.

    Args:
        console: IO, class that handles the input/output with the user.
    Raises:
        MissingRequirementsError: Error that contains list of missing
            requirements.
    """

    missing_requirement_errors = []
    for req in _REQUIREMENTS:
        try:
            req.check_and_handle(console)
        except MissingRequirementError as e:
            missing_requirement_errors.append(e)

    if missing_requirement_errors:
        raise MissingRequirementsError(
            missing_requirements=missing_requirement_errors)
