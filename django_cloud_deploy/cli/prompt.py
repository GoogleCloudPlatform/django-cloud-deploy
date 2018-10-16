# Copyright 2018 Google LLC
#
# Licensed under the Apache License, Versconsolen 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITconsoleNS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissconsolens and
# limitatconsolens under the License.
"""Prompts the user for information e.g. project name."""

import abc
import os.path
import random
import re
import string
from typing import Any, Dict

from google.auth import credentials

from django_cloud_deploy.cli import io
from django_cloud_deploy.cloudlib import auth


class Prompt(object):
    """Base class for classes the collect user input from the console."""

    @classmethod
    @abc.abstractmethod
    def prompt(cls, console: io.IO, step_prompt: str,
               arguments: Dict[str, Any]) -> Any:
        """Prompt the user to enter some information.

    Args:
      console: Object to use for user I/O.
      step_prompt: A prefix showing the current step number e.g. "[1/3]".
      arguments: The arguments that have already been collected from the user
        e.g. {"project_id", "project-123"}

    Returns:
      The value entered by the user.
    """

    @staticmethod
    def validate(s: str):
        """Validates that a string is valid for this prompt type.

    Args:
      s: The string to validate.

    Raises:
      ValueError: if the input string is not valid.
    """
        pass


class NamePrompt(Prompt):
    """Base class for classes that prompt for some sort of name.

  Subclasses must:
  1. set _PROMPT to the prompt text.
  2. implement _default_name()
  3. implement validate.
  """

    _PROMPT = None

    @staticmethod
    @abc.abstractmethod
    def _default_name(arguments: Dict[str, Any]):
        """The default name to use."""

    @classmethod
    def prompt(cls, console: io.IO, step_prompt: str,
               arguments: Dict[str, Any]) -> str:
        """Prompt the user to enter some sort of name.

    Args:
      console: Object to use for user I/O.
      step_prompt: A prefix showing the current step number e.g. "[1/3]".
      arguments: The arguments that have already been collected from the user
        e.g. {"project_id", "project-123"}

    Returns:
      The value entered by the user.
    """
        default_name = cls._default_name(arguments)
        while True:
            console.tell(('{} {}').format(step_prompt, cls._PROMPT))
            project_name = console.ask('[{}]: '.format(default_name))
            if not project_name.strip():
                project_name = default_name
            try:
                cls.validate(project_name)
            except ValueError as e:
                console.error(e)
                continue
            return project_name


class GoogleCloudProjectNamePrompt(NamePrompt):
    """Allow the user to enter a GCP project name."""

    _PROMPT = ('Enter a Google Cloud Platform project name, or leave '
               'blank to use')

    @classmethod
    def _default_name(cls, arguments: Dict[str, Any]):
        return 'Django Project'

    @staticmethod
    def validate(s):
        """Validates that a string is a valid project name.

    Args:
      s: The string to validate.

    Raises:
      ValueError: if the input string is not valid.
    """
        if not (4 <= len(s) <= 30):
            raise ValueError(
                ('Invalid Google Cloud Platform project name "{}": '
                 'must be between 4 and 30 characters').format(s))


class DjangoProjectNamePrompt(NamePrompt):
    """Allow the user to enter a Django project name."""

    _PROMPT = 'Enter a Django project name, or leave blank to use'

    @classmethod
    def _default_name(cls, arguments: Dict[str, Any]):
        return 'mysite'

    @staticmethod
    def validate(s):
        """Validates that a string is a valid Django project name.

    Args:
      s: The string to validate.

    Raises:
      ValueError: if the input string is not valid.
    """
        if not s.isidentifier():
            raise ValueError(('Invalid Django project name "{}": '
                              'must be a valid Python identifier').format(s))


class DjangoAppNamePrompt(NamePrompt):
    """Allow the user to enter a Django app name."""

    _PROMPT = 'Enter a Django app name, or leave blank to use'

    @classmethod
    def _default_name(cls, arguments: Dict[str, Any]):
        return 'home'

    @staticmethod
    def validate(s):
        """Validates that a string is a valid Django app name.

    Args:
      s: The string to validate.

    Raises:
      ValueError: if the input string is not valid.
    """
        if not s.isidentifier():
            raise ValueError(('Invalid Django app name "{}": '
                              'must be a valid Python identifier').format(s))


class DjangoSuperuserLoginPrompt(NamePrompt):
    """Allow the user to enter a Django superuser login."""

    _PROMPT = 'Enter a name for the Django superuser, or leave blank to use'

    @classmethod
    def _default_name(cls, arguments: Dict[str, Any]):
        return 'admin'

    @staticmethod
    def validate(s):
        """Validates that a string is a valid Django superuser login.

    Args:
      s: The string to validate.

    Raises:
      ValueError: if the input string is not valid.
    """
        if not s.isalnum():
            raise ValueError(('Invalid Django superuser login "{}": '
                              'must be a alpha numeric').format(s))


class DjangoSuperuserEmailPrompt(NamePrompt):
    """Allow the user to enter a Django email address."""

    _PROMPT = ('Enter a e-mail address for the Django superuser, '
               'or leave blank to use')

    @classmethod
    def _default_name(cls, arguments: Dict[str, Any]):
        return 'test@example.com'

    @staticmethod
    def validate(s):
        """Validates that a string is a valid Django superuser email address.

    Args:
      s: The string to validate.

    Raises:
      ValueError: if the input string is not valid.
    """
        if not re.match(r'[^@]+@[^@]+\.[^@]+', s):
            raise ValueError(('Invalid Django superuser email address "{}": '
                              'the format should be like '
                              '"test@example.com"').format(s))


class ProjectIdPrompt(Prompt):
    """Allow the user to enter a GCP project id."""

    @staticmethod
    def _generate_default_project_id(project_name=None):
        default_project_id = (project_name or 'django').lower()
        default_project_id = default_project_id.replace(' ', '-')
        if default_project_id[0] not in string.ascii_lowercase:
            default_project_id = 'django-' + default_project_id
        default_project_id = re.sub('[^a-z0-9\-]', '', default_project_id)

        return '{0}-{1}'.format(default_project_id[0:30 - 6 - 1],
                                random.randint(100000, 1000000))

    @classmethod
    def prompt(cls, console: io.IO, step_prompt: str,
               arguments: Dict[str, Any]) -> str:
        """Prompt the user to a Google Cloud Platform project id.

    Args:
      console: Object to use for user I/O.
      step_prompt: A prefix showing the current step number e.g. "[1/3]".
      arguments: The arguments that have already been collected from the user
        e.g. {"project_id", "project-123"}

    Returns:
      The value entered by the user.
    """
        default_project_id = cls._generate_default_project_id(
            arguments.get('project_name'))
        while True:
            console.tell(('{} Enter a Google Cloud Platform Project ID, '
                          'or leave blank to use').format(step_prompt))
            project_id = console.ask('[{}]: '.format(default_project_id))
            if not project_id.strip():
                return default_project_id
            try:
                cls.validate(project_id)
            except ValueError as e:
                console.error(e)
                continue
            return project_id

    @staticmethod
    def validate(s):
        """Validates that a string is a valid project id.

    Args:
      s: The string to validate.

    Raises:
      ValueError: if the input string is not valid.
    """
        if not re.match(r'[a-z][a-z0-9\-]{5,29}', s):
            raise ValueError(('Invalid Google Cloud Platform Project ID "{}": '
                              'must be between 6 and 30 characters and contain '
                              'lowercase letters, digits or hyphens').format(s))


class DjangoFilesystemPath(Prompt):
    """Allow the user to file system path for their project."""

    @staticmethod
    def _prompt_replace(console, directory):
        while True:
            r = console.ask(("The directory \'{}\' already exists, "
                             "replace it's contents [y/N]: ").format(directory))
            r = r.strip().lower() or 'n'
            if r not in ['n', 'y']:
                continue
            return r == 'y'

    @classmethod
    def prompt(cls, console: io.IO, step_prompt: str,
               arguments: Dict[str, Any]) -> str:
        """Prompt the user to enter a file system path for their project.

    Args:
      console: Object to use for user I/O.
      step_prompt: A prefix showing the current step number e.g. "[1/3]".
      arguments: The arguments that have already been collected from the user
        e.g. {"project_id", "project-123"}

    Returns:
      The value entered by the user.
    """
        home_dir = os.path.expanduser('~')
        # TODO: Remove filesystem-unsafe characters. Implement a validation
        # method that checks for these.
        default_directory = os.path.join(
            home_dir,
            arguments.get('project_name', 'django-project').lower().replace(
                ' ', '-'))

        while True:
            console.tell('{} Enter a directory or leave blank to use'.format(
                step_prompt))
            directory = console.ask('[{}]: '.format(default_directory))
            if not directory.strip():
                directory = default_directory
            try:
                cls.validate(directory)
            except ValueError as e:
                console.error(e)
                continue

            if os.path.exists(directory):
                if not cls._prompt_replace(console, directory):
                    continue
            return directory


class PasswordPrompt(Prompt):
    """Base class for classes that prompt for a password.

  Subclasses must:
  1. implement _get_prompt()
  2. implement _default_name()
  3. implement validate()
  """

    @classmethod
    @abc.abstractmethod
    def _get_prompt(cls, arguments: Dict[str, Any]) -> str:
        pass

    @classmethod
    def prompt(cls, console: io.IO, step_prompt: str,
               arguments: Dict[str, Any]) -> str:
        """Prompt the user to enter a password.

    Args:
      console: Object to use for user I/O.
      step_prompt: A prefix showing the current step number e.g. "[1/3]".
      arguments: The arguments that have already been collected from the user
        e.g. {"project_id", "project-123"}

    Returns:
      The value entered by the user.
    """
        console_prompt = cls._get_prompt(arguments)
        console.tell(('{} {}').format(step_prompt, console_prompt))
        while True:
            password1 = console.getpass('Password: ')
            try:
                cls.validate(password1)
            except ValueError as e:
                console.error(e)
                continue
            password2 = console.getpass('Password (again): ')
            if password1 != password2:
                console.error('Passwords do not match, please try again')
                continue
            return password1

    @staticmethod
    def validate(s):
        """Validates that a string is a valid password.

    Args:
      s: The string to validate.

    Raises:
      ValueError: if the input string is not valid.
    """
        if len(s) < 5:
            raise ValueError('Passwords must be at least 6 characters long')
        allowed_characters = frozenset(string.ascii_letters + string.digits +
                                       string.punctuation)
        if frozenset(s).issuperset(allowed_characters):
            raise ValueError('Invalid character in password: '
                             'use letters, numbers and punctuation')


class PostgresPasswordPrompt(PasswordPrompt):
    """Allow the user to enter a Django Postgres password."""

    @classmethod
    def _get_prompt(cls, arguments: Dict[str, Any]) -> str:
        return 'Enter a password for the default database user "postgres"'


class DjangoSuperuserPasswordPrompt(PasswordPrompt):
    """Allow the user to enter a password for the Django superuser."""

    @classmethod
    def _get_prompt(cls, arguments: Dict[str, Any]) -> str:
        if 'django_superuser_login' in arguments:
            return 'Enter a password for the Django superuser "{}"'.format(
                arguments['django_superuser_login'])
        else:
            return 'Enter a password for the Django superuser'


class CredentialsPrompt(Prompt):

    @classmethod
    def prompt(cls, console: io.IO, step_prompt: str,
               arguments: Dict[str, Any]) -> credentials.Credentials:
        """Prompt the user for access to the Google credentials.

    Args:
      console: Object to use for user I/O.
      step_prompt: A prefix showing the current step number e.g. "[1/3]".
      arguments: The arguments that have already been collected from the user
        e.g. {"project_id", "project-123"}

    Returns:
      The user's credentials.
    """
        console.tell(
            ('{} In order to deploy your application, you must allow Django '
             'Deploy to access your Google account.').format(step_prompt))
        console.ask('Press [Enter] to open a browser window to allow access')
        auth_client = auth.AuthClient()
        auth_client.gcloud_login()
        auth_client.authenticate_docker()
        return auth_client.create_default_credentials()
