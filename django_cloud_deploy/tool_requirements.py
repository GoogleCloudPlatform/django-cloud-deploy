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
import grp
import os
import shutil
import subprocess
import sys

import pexpect
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
            except UnableToAutomaticallyInstallError as e:
                raise MissingRequirementError(e.name, e.how_to_install_message)
            except NotImplementedError:
                raise missing_requirement_error


class Gcloud(Requirement):
    NAME = 'Gcloud SDK'

    @classmethod
    def check(cls):
        """Checks if Gcloud SDK is installed.

        Raises:
            MissingRequirementError: If the requirement is not found.
        """
        if shutil.which('gcloud'):
            return None

        # Default paths
        gcloud_config_path = os.path.expanduser('~/.config/gcloud')
        gcloud_sdk_path = os.path.expanduser('~/google-cloud-sdk/gcloud')
        gcloud_sdk_apt_get_path = '/usr/bin/gcloud'

        path_exists = (os.path.exists(gcloud_config_path) or
                       os.path.exists(gcloud_sdk_path) or
                       os.path.exists(gcloud_sdk_apt_get_path))
        download_link = (
            'https://cloud.google.com/sdk/docs/downloads-interactive')
        if path_exists:
            msg = ('It seems you have downloaded gcloud already, please try '
                   'again on a new terminal. If you have uninstalled, please '
                   'install from {}'.format(download_link))
            raise MissingRequirementError(cls.NAME, msg)

        msg = ('Please install Google Cloud SDK from {} and open a new '
               'terminal once downloaded'.format(download_link))
        raise MissingRequirementError(cls.NAME, msg)


class Docker(Requirement):
    NAME = 'Docker'

    _LINUX_NOT_IN_GROUP_MESSAGE = (
        'Docker is installed but not useable.\n\n'
        'It may be that you need to add yourself to the "docker" group.\n'
        'You can do so by running the following commands: \n'
        'sudo groupadd docker\n'
        'sudo usermod -a -G docker $USER\n'
        'IMPORTANT: Log out and log back in so that your group membership is '
        're-evaluated.\n\n'
        'For Docker post-installation information, see: '
        'https://docs.docker.com/install/linux/linux-postinstall/')

    _LINUX_GENERIC_NOT_USABLE_MESSAGE = (
        'Docker is installed but not useable (is it running?).\n\n'
        'For Docker post-installation information, see: '
        'https://docs.docker.com/install/linux/linux-postinstall/')

    _MAC_GENERIC_NOT_USABLE_MESSAGE = (
        'Docker is installed but not useable (is it running?).\n\n'
        'For Docker troubleshooting information, see: '
        'https://docs.docker.com/docker-for-mac/troubleshoot/')

    _WINDOWS_GENERIC_NOT_USABLE_MESSAGE = (
        'Docker is installed but not useable (is it running?).\n\n'
        'For Docker troubleshooting information, see: '
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
            download_link = 'https://store.docker.com/'
            msg = 'Please download Docker from {}'.format(download_link)
            raise MissingRequirementError(cls.NAME, msg)

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
                        cls.NAME,
                        cls._LINUX_NOT_IN_GROUP_MESSAGE)
                else:
                    raise MissingRequirementError(
                        cls.NAME,
                        cls._LINUX_GENERIC_NOT_USABLE_MESSAGE)
            elif sys.platform.startswith('darwin'):
                raise MissingRequirementError(
                    cls.NAME,
                    cls._MAC_GENERIC_NOT_USABLE_MESSAGE)
            elif sys.platform.startswith('win32'):
                raise MissingRequirementError(
                    cls.NAME,
                    cls._WINDOWS_GENERIC_NOT_USABLE_MESSAGE)



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
        """
        if shutil.which('gcloud') is None:
            msg = "Gcloud is needed to install Cloud Sql Proxy"
            raise UnableToAutomaticallyInstallError(cls.NAME, msg)

        while True:
            answer = console.ask('Cloud Sql Proxy is required by Django Cloud '
                                 'Deploy. Would you like us to install '
                                 'automatically (Y/n)? ').lower().strip()
            if answer not in ['y', 'n']:
                continue
            if answer == 'n':
                raise NotImplementedError
            break

        try:
            args = ['components', 'install', 'cloud_sql_proxy']
            process = pexpect.spawn('gcloud', args)
            process.expect('Do you want to continue (Y/n)?')
            process.sendline('Y')
            process.expect('Update done!')
        except (pexpect.exceptions.TIMEOUT, pexpect.exceptions.EOF):
            dl_link = 'https://cloud.google.com/sql/docs/mysql/sql-proxy'
            msg = ('Unable to download Cloud Sql Proxy directly from Gcloud. '
                   'This is caused when Gcloud was not downloaded directly from'
                   ' https://cloud.google.com/sdk/docs/downloads-interactive\n'
                   'Please install Cloud SQL Proxy from {}').format(dl_link)
            raise UnableToAutomaticallyInstallError(cls.NAME, msg)
        finally:
            process.close()


_REQUIREMENTS = {
    'gke': [
        Gcloud,
        Docker,
        CloudSqlProxy
    ],
    'gae': [
        Gcloud,
        CloudSqlProxy
    ]
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
            # TODO: Update test to match prompt. For example, this does not read
            # well:
            # Docker must be installed.
            #
            # Docker is installed but...
            console.tell('{} must be installed.\n\n{}'.format(
                e.name, e.how_to_install_message))
            return False
    return True
