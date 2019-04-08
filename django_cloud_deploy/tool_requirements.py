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
"""Checks the user has the necessary requirements to run the tool."""

import getpass
import os
import shutil
import subprocess
import sys

from typing import List

from django_cloud_deploy.cli import io


class UnableToAutomaticallyInstallError(Exception):
    """Thrown when the handle function is unable to install the requirement."""

    def __init__(self, name: str, how_to_install_message: str):
        """Provides information on how to manually install the requirement.

        Args:
            name: Name of the requirement.
            how_to_install_message: Information to help user to install
                the requirement.
        """
        self.name = name
        self.how_to_install_message = how_to_install_message


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
        If unsuccessful, provides information on how to manually install.

        Raises:
            MissingRequirementError: If the requirement needs to be
                installed manually.
        """
        try:
            cls.check()
        except MissingRequirementError as missing_requirement_error:
            try:
                cls.handle(console)
            except UnableToAutomaticallyInstallError as e:
                raise MissingRequirementError(e.name, e.how_to_install_message)
            except NotImplementedError:
                raise missing_requirement_error


class Gcloud(Requirement):
    NAME = 'Gcloud SDK'

    _NOT_INSTALLED = ('The Google Cloud SDK is not installed.\n\n'
                      'You can install it using the instructions at:\n'
                      'https://cloud.google.com/sdk/docs/downloads-interactive')

    _INSTALLED_BUT_NOT_ON_PATH = (
        'The Google Cloud SDK is installed at "{0}"\n'
        'but is not on the PATH.\n\n'
        'You can either add it to the PATH or reinstall it using the '
        'instructions at:\n'
        'https://cloud.google.com/sdk/docs/downloads-interactive')

    @classmethod
    def check(cls):
        """Checks if Gcloud SDK is installed.

        Raises:
            MissingRequirementError: If the requirement is not found.
        """
        if shutil.which('gcloud'):
            return None

        # Default paths
        common_gcloud_paths = [
            os.path.expanduser('~/.config/gcloud'),
            os.path.expanduser('~/google-cloud-sdk/gcloud'), '/usr/bin/gcloud'
        ]
        gcloud_path = None
        for path in common_gcloud_paths:
            if os.path.exists(path):
                gcloud_path = path

        if gcloud_path:
            raise MissingRequirementError(
                cls.NAME, cls._INSTALLED_BUT_NOT_ON_PATH.format(gcloud_path))

        raise MissingRequirementError(cls.NAME, cls._NOT_INSTALLED)


class Docker(Requirement):
    NAME = 'Docker'

    _NOT_INSTALLED = ('Docker is not installed.\n\n'
                      'You can install it using the instructions at:\n'
                      'https://store.docker.com/')

    _LINUX_NOT_IN_GROUP_MESSAGE = (
        'Docker is installed but not useable.\n\n'
        'It may be that you need to add yourself to the "docker" group.\n'
        'You can do so by running the following commands:\n'
        'sudo groupadd docker\n'
        'sudo usermod -a -G docker $USER\n'
        'IMPORTANT: Log out and log back in so that your group membership is '
        're-evaluated.\n\n'
        'For Docker post-installation information, see:\n'
        'https://docs.docker.com/install/linux/linux-postinstall/')

    _LINUX_GENERIC_NOT_USABLE_MESSAGE = (
        'Docker is installed but not useable (is it running?).\n\n'
        'For Docker post-installation information, see:\n'
        'https://docs.docker.com/install/linux/linux-postinstall/')

    _MAC_GENERIC_NOT_USABLE_MESSAGE = (
        'Docker is installed but not useable (is it running?).\n\n'
        'For Docker troubleshooting information, see:\n'
        'https://docs.docker.com/docker-for-mac/troubleshoot/')

    _WINDOWS_GENERIC_NOT_USABLE_MESSAGE = (
        'Docker is installed but not useable (is it running?).\n\n'
        'For Docker troubleshooting information, see:\n'
        'https://docs.docker.com/docker-for-windows/troubleshoot/')

    @staticmethod
    def _is_usable():
        """Return True if Docker is useable, False otherwise."""

        command = ['docker', 'image', 'ls']
        return subprocess.call(command,
                               stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL) == 0

    @staticmethod
    def _is_missing_group_membership():
        """Returns True if a 'docker' group exists and the user isn't in it."""
        import grp  # Not available on Windows

        try:
            docker_group = grp.getgrnam('docker')
        except KeyError:
            return False

        user = getpass.getuser()
        return user not in docker_group.gr_mem

    @classmethod
    def check(cls):
        """Checks if Docker is installed and useable.

        Raises:
            MissingRequirementError: If the requirement is not found.
        """
        if not shutil.which('docker'):
            raise MissingRequirementError(cls.NAME, cls._NOT_INSTALLED)

        if not cls._is_usable():
            # Docker is installed but not useable. There are many possible
            # causes e.g. the docker server is not running, the user does not
            # have permissions to access the docker server. Try to narrow down
            # the cause as much as possible and display a helpful error message.
            if sys.platform.startswith('linux'):
                if cls._is_missing_group_membership():
                    # Docker is installed and there is a 'docker' group in the
                    # UNIX group database but the user isn't part of that group.
                    # By default, the user has to either run docker as root
                    # or be a member of that group.
                    raise MissingRequirementError(
                        cls.NAME, cls._LINUX_NOT_IN_GROUP_MESSAGE)
                else:
                    raise MissingRequirementError(
                        cls.NAME, cls._LINUX_GENERIC_NOT_USABLE_MESSAGE)
            elif sys.platform.startswith('darwin'):
                raise MissingRequirementError(
                    cls.NAME, cls._MAC_GENERIC_NOT_USABLE_MESSAGE)
            elif sys.platform.startswith('win32'):
                raise MissingRequirementError(
                    cls.NAME, cls._WINDOWS_GENERIC_NOT_USABLE_MESSAGE)


class CloudSqlProxy(Requirement):
    NAME = 'Cloud SQL Proxy'

    _NOT_INSTALLED = (
        'Cloud SQL Proxy is not installed.\n\n'
        'You can install it using the instructions at:\n'
        'https://cloud.google.com/sql/docs/mysql/sql-proxy#install')

    _AUTOMATIC_INSTALLATION_ERROR = (
        'Unable to install Cloud SQL Proxy automatically using the command:\n'
        '    gcloud components install cloud_sql_proxy\n\n'
        'For manual installation instructions, see:\n'
        'https://cloud.google.com/sql/docs/mysql/sql-proxy#install\n\n'
        'NOTE: cloud_sql_proxy must be added to the PATH for it to be useable.')

    _OLD_GCLOUD_VERSION = (
        'Unable to install Cloud SQL Proxy automatically using the command:\n'
        '    gcloud components install cloud_sql_proxy\n\n'
        'The installed version of gcloud is too old. You can upgrade it '
        'using the command:\n'
        '    gcloud components update\n\n')

    _MUST_INSTALL_INTERACTIVE = (
        'Unable to install Cloud SQL Proxy automatically using the command:\n'
        '    gcloud components install cloud_sql_proxy\n\n'
        'You can run this command yourself or follow the manual installation'
        'instructions at:\n'
        'https://cloud.google.com/sql/docs/mysql/sql-proxy#install\n\n'
        'NOTE: in the manual installation case, cloud_sql_proxy must be '
        'added to the PATH for it to be useable.')

    @classmethod
    def check(cls):
        """Checks if Cloud SQL Proxy is installed.

        Raises:
            MissingRequirementError: If the requirement is not found.
        """
        if not shutil.which('cloud_sql_proxy'):
            raise MissingRequirementError(cls.NAME, cls._NOT_INSTALLED)

    @classmethod
    def handle(cls, console: io.IO):
        """Attempts to install the requirement.

        Raises:
            UnableToAutomaticallyInstall: If the installation fails.
        """
        gcloud_path = shutil.which('gcloud')
        if gcloud_path is None:
            msg = "gcloud is needed to install Cloud SQL Proxy"
            raise UnableToAutomaticallyInstallError(cls.NAME, msg)

        while True:
            answer = console.ask('Cloud SQL Proxy is required by Django '
                                 'Deploy. Would you like us to install it '
                                 'automatically (Y/n)? ').lower().strip()
            if answer == 'n':
                raise NotImplementedError
            elif answer in ['y', '']:
                break

        command = [
            gcloud_path, '-q', 'components', 'install', 'cloud_sql_proxy'
        ]
        install_result = subprocess.run(command,
                                        stdout=subprocess.DEVNULL,
                                        stderr=subprocess.PIPE,
                                        universal_newlines=True)
        if install_result.returncode != 0:
            if 'gcloud components update' in install_result.stderr:
                raise UnableToAutomaticallyInstallError(cls.NAME,
                                                        cls._OLD_GCLOUD_VERSION)
            elif 'non-interactive mode' in install_result.stderr:
                raise UnableToAutomaticallyInstallError(
                    cls.NAME, cls._MUST_INSTALL_INTERACTIVE)
            else:
                raise UnableToAutomaticallyInstallError(
                    cls.NAME, cls._AUTOMATIC_INSTALLATION_ERROR)


_REQUIREMENTS = {
    'gke': [Gcloud, Docker, CloudSqlProxy],
    'gae': [Gcloud, CloudSqlProxy]
}


def check_and_handle_requirements(console: io.IO, backend: str) -> bool:
    """Checks that requirements are installed. Attempts to install missing ones.

    Args:
        console: Handles the input/output with the user.
        backend: Defines which platform on determines what requirements are
            needed. Options are 'gke' and 'gae'.

    Returns:
        True if all requirements have been satisfied, False otherwise.
    """
    for req in _REQUIREMENTS[backend]:
        try:
            req.check_and_handle(console)
        except MissingRequirementError as e:
            console.error(e.how_to_install_message)
            return False
    return True
