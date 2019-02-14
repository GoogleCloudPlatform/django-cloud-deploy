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
import time
from typing import Any, Dict, List, Optional
import webbrowser

from google.auth import credentials

from django_cloud_deploy import workflow
from django_cloud_deploy.cli import io
from django_cloud_deploy.cloudlib import auth
from django_cloud_deploy.cloudlib import billing
from django_cloud_deploy.cloudlib import project
from django_cloud_deploy.skeleton import utils


class Prompt(object):
    """Base class for classes the collect user input from the console."""

    @classmethod
    @abc.abstractmethod
    def prompt(cls,
               console: io.IO,
               step_prompt: str,
               arguments: Dict[str, Any],
               credentials: Optional[credentials.Credentials] = None) -> Any:
        """Prompt the user to enter some information.

        Args:
            console: Object to use for user I/O.
            step_prompt: A prefix showing the current step number e.g. "[1/3]".
            arguments: The arguments that have already been collected from the
                user e.g. {"project_id", "project-123"}
            credentials: The OAuth2 Credentials object to use for api calls
                during prompt.

        Returns:
            The value entered by the user.
        """

    @staticmethod
    def validate(s: str, credentials: Optional[credentials.Credentials] = None):
        """Validates that a string is valid for this prompt type.

        Args:
            s: The string to validate.
            credentials: The OAuth2 Credentials object to use for api calls
                during validation.

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
    def prompt(cls,
               console: io.IO,
               step_prompt: str,
               arguments: Dict[str, Any],
               credentials: Optional[credentials.Credentials] = None) -> str:
        """Prompt the user to enter some sort of name.

        Args:
            console: Object to use for user I/O.
            step_prompt: A prefix showing the current step number e.g. "[1/3]".
            arguments: The arguments that have already been collected from the
                user e.g. {"project_id", "project-123"}
            credentials: The OAuth2 Credentials object to use for api calls
                during prompt.

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

    @classmethod
    def prompt(cls,
               console: io.IO,
               step_prompt: str,
               arguments: Dict[str, Any],
               credentials: Optional[credentials.Credentials] = None) -> str:

        if ('project_creation_mode' not in arguments or
            (arguments['project_creation_mode'] !=
             workflow.ProjectCreationMode.MUST_EXIST)):
            return (super().prompt(console, step_prompt, arguments,
                                   credentials))

        assert 'project_id' in arguments, 'project_id must be set'
        project_id = arguments['project_id']
        project_client = project.ProjectClient.from_credentials(credentials)
        project_name = project_client.get_project(project_id)['name']
        message = 'Project name found: {}'.format(project_name)
        console.tell(('{} {}').format(step_prompt, message))
        return project_name

    @staticmethod
    def validate(s, credentials: Optional[credentials.Credentials] = None):
        """Validates that a string is a valid project name.

        Args:
            s: The string to validate.
            credentials: The OAuth2 Credentials object to use for api calls
                during validation.

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
    def validate(s, credentials: Optional[credentials.Credentials] = None):
        """Validates that a string is a valid Django project name.

        Args:
            s: The string to validate.
            credentials: The OAuth2 Credentials object to use for api calls
                during validation.

        Raises:
            ValueError: if the input string is not valid.
        """
        if not s.isidentifier():
            raise ValueError(('Invalid Django project name "{}": '
                              'must be a valid Python identifier').format(s))


class DjangoProjectNameUpdatePrompt(DjangoProjectNamePrompt):
    """Allow the user to enter a Django project name."""

    _PROMPT = 'Enter the Django project name you want to update.'


class DjangoAppNamePrompt(NamePrompt):
    """Allow the user to enter a Django app name."""

    _PROMPT = 'Enter a Django app name, or leave blank to use'

    @classmethod
    def _default_name(cls, arguments: Dict[str, Any]):
        return 'home'

    @staticmethod
    def validate(s, credentials: Optional[credentials.Credentials] = None):
        """Validates that a string is a valid Django app name.

        Args:
            s: The string to validate.
            credentials: The OAuth2 Credentials object to use for api calls
                during validation.

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
    def validate(s, credentials: Optional[credentials.Credentials] = None):
        """Validates that a string is a valid Django superuser login.

        Args:
            s: The string to validate.
            credentials: The OAuth2 Credentials object to use for api calls
                during validation.

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
    def validate(s, credentials: Optional[credentials.Credentials] = None):
        """Validates that a string is a valid Django superuser email address.

        Args:
            s: The string to validate.
            credentials: The OAuth2 Credentials object to use for api calls
                during validation.

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
        default_project_id = re.sub(r'[^a-z0-9\-]', '', default_project_id)

        return '{0}-{1}'.format(default_project_id[0:30 - 6 - 1],
                                random.randint(100000, 1000000))

    @classmethod
    def prompt(cls,
               console: io.IO,
               step_prompt: str,
               arguments: Dict[str, Any],
               credentials: Optional[credentials.Credentials] = None) -> str:
        """Prompt the user to a Google Cloud Platform project id.

        Args:
            console: Object to use for user I/O.
            step_prompt: A prefix showing the current step number e.g. "[1/3]".
            arguments: The arguments that have already been collected from the
                user e.g. {"project_id", "project-123"}
            credentials: The OAuth2 Credentials object to use for api calls
                during prompt.

        Returns:
            The value entered by the user.
        """
        default_project_id = cls._generate_default_project_id(
            arguments.get('project_name', None))
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
    def validate(s, credentials: Optional[credentials.Credentials] = None):
        """Validates that a string is a valid project id.

        Args:
            s: The string to validate.
            credentials: The OAuth2 Credentials object to use for api calls
                during validation.

        Raises:
            ValueError: if the input string is not valid.
        """
        if not re.match(r'[a-z][a-z0-9\-]{5,29}', s):
            raise ValueError(('Invalid Google Cloud Platform Project ID "{}": '
                              'must be between 6 and 30 characters and contain '
                              'lowercase letters, digits or hyphens').format(s))


class ExistingProjectIdPrompt(ProjectIdPrompt):
    """Allow the user to enter a GCP project id."""

    @classmethod
    def prompt(cls,
               console: io.IO,
               step_prompt: str,
               arguments: Dict[str, Any],
               credentials: Optional[credentials.Credentials] = None) -> str:
        """Prompt the user to a Google Cloud Platform project id.

        If the user supplies the project_id as a flag we want to validate that
        it exists. We tell the user to supply a new one if it does not.

        Args:
            console: Object to use for user I/O.
            step_prompt: A prefix showing the current step number e.g. "[1/3]".
            arguments: The arguments that have already been collected from the
                user e.g. {"project_id", "project-123"}
            credentials: The OAuth2 Credentials object to use for api calls
                during prompt.

        Returns:
            The value entered by the user.
        """
        project_id = arguments.get('project_id', None)
        valid_project_id = False
        while not valid_project_id:
            if not project_id:
                console.tell(
                    ('{} Enter the existing Google Cloud Platform Project ID '
                     'to use.').format(step_prompt))
                project_id = console.ask('Project ID: ')
            try:
                cls.validate(project_id, credentials)
                if (arguments.get(
                        'project_creation_mode',
                        False) == workflow.ProjectCreationMode.MUST_EXIST):
                    console.tell(('{} Google Cloud Platform Project ID {}'
                                  ' is valid').format(step_prompt, project_id))
                valid_project_id = True
            except ValueError as e:
                console.error(e)
                project_id = None
                continue
        return project_id

    @staticmethod
    def validate(s, credentials: Optional[credentials.Credentials] = None):
        """Validates that a string is a valid project id.

        Args:
            s: The string to validate.
            credentials: The OAuth2 Credentials object to use for api calls
                during validation.

        Raises:
            ValueError: if the input string is not valid.
        """
        if not re.match(r'[a-z][a-z0-9\-]{5,29}', s):
            raise ValueError(('Invalid Google Cloud Platform Project ID "{}": '
                              'must be between 6 and 30 characters and contain '
                              'lowercase letters, digits or hyphens').format(s))

        project_client = project.ProjectClient.from_credentials(credentials)
        if not project_client.project_exists(s):
            raise ValueError('Project {} does not exist'.format(s))


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
    def prompt(cls,
               console: io.IO,
               step_prompt: str,
               arguments: Dict[str, Any],
               credentials: Optional[credentials.Credentials] = None) -> str:
        """Prompt the user to enter a file system path for their project.

        Args:
            console: Object to use for user I/O.
            step_prompt: A prefix showing the current step number e.g. "[1/3]".
            arguments: The arguments that have already been collected from the
                user e.g. {"project_id", "project-123"}
            credentials: The OAuth2 Credentials object to use for api calls
                during prompt.

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
            console.tell(
                ('{} Enter a new directory path to store project source, '
                 'or leave blank to use').format(step_prompt))
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


class DjangoFilesystemPathUpdate(Prompt):
    """Allow the user to file system path for their project."""

    @classmethod
    def prompt(cls,
               console: io.IO,
               step_prompt: str,
               arguments: Dict[str, Any],
               credentials: Optional[credentials.Credentials] = None) -> str:
        """Prompt the user to enter a file system path for their project.

        Args:
            console: Object to use for user I/O.
            step_prompt: A prefix showing the current step number e.g. "[1/3]".
            arguments: The arguments that have already been collected from the
                user e.g. {"project_id", "project-123"}
            credentials: The OAuth2 Credentials object to use for api calls
                during prompt.

        Returns:
            The value entered by the user.
        """
        home_dir = os.path.expanduser('~')
        default_directory = os.path.join(
            home_dir,
            arguments.get('project_name', 'django-project').lower().replace(
                ' ', '-'))

        while True:
            console.tell(
                ('{} Enter the directory of the Django project you want to '
                 'update:'.format(step_prompt)))
            directory = console.ask('[{}]: '.format(default_directory))
            if not directory.strip():
                directory = default_directory
            directory = os.path.abspath(os.path.expanduser(directory))

            try:
                cls.validate(directory)
            except ValueError as e:
                console.error(e)
                continue

            return directory

    @staticmethod
    def validate(s, credentials: Optional[credentials.Credentials] = None):
        """Validates that a string is a valid directory path.

        Args:
            s: The string to validate.
            credentials: The OAuth2 Credentials object to use for api calls
                during validation.

        Raises:
            ValueError: if the input string is not valid.
        """
        if not os.path.exists(s):
            raise ValueError(('Path ["{}"] does not exist.').format(s))

        if not utils.is_valid_django_project(s):
            raise ValueError(
                ('Path ["{}"] does not contain a valid Django project.'
                ).format(s))


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
    def prompt(cls,
               console: io.IO,
               step_prompt: str,
               arguments: Dict[str, Any],
               credentials: Optional[credentials.Credentials] = None) -> str:
        """Prompt the user to enter a password.

        Args:
            console: Object to use for user I/O.
            step_prompt: A prefix showing the current step number e.g. "[1/3]".
            arguments: The arguments that have already been collected from the
                user e.g. {"project_id", "project-123"}
            credentials: The OAuth2 Credentials object to use for api calls
                during prompt.

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
    def validate(s, credentials: Optional[credentials.Credentials] = None):
        """Validates that a string is a valid password.

        Args:
            s: The string to validate.
            credentials: The OAuth2 Credentials object to use for api calls
                during validation.

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


class PostgresPasswordUpdatePrompt(PasswordPrompt):
    """Allow the user to enter a Django Postgres password."""

    @classmethod
    def _get_prompt(cls, arguments: Dict[str, Any]) -> str:
        return 'Enter the password for the default database user "postgres"'

    @classmethod
    def prompt(cls,
               console: io.IO,
               step_prompt: str,
               arguments: Dict[str, Any],
               credentials: Optional[credentials.Credentials] = None) -> str:
        """Prompt the user to enter a password.

        Args:
            console: Object to use for user I/O.
            step_prompt: A prefix showing the current step number e.g. "[1/3]".
            arguments: The arguments that have already been collected from the
                user e.g. {"project_id", "project-123"}
            credentials: The OAuth2 Credentials object to use for api calls
                during prompt.

        Returns:
            The value entered by the user.
        """
        console_prompt = cls._get_prompt(arguments)
        console.tell(('{} {}').format(step_prompt, console_prompt))
        while True:
            password = console.getpass('Postgres password: ')
            try:
                cls.validate(password)
            except ValueError as e:
                console.error(e)
                continue
            return password


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
    def prompt(cls,
               console: io.IO,
               step_prompt: str,
               arguments: Dict[str, Any],
               credentials: Optional[credentials.Credentials] = None
              ) -> credentials.Credentials:
        """Prompt the user for access to the Google credentials.

        Args:
            console: Object to use for user I/O.
            step_prompt: A prefix showing the current step number e.g. "[1/3]".
            arguments: The arguments that have already been collected from the
                user e.g. {"project_id", "project-123"}
            credentials: The OAuth2 Credentials object to use for api calls
                during prompt.

        Returns:
            The user's credentials.
        """
        console.tell(
            ('{} In order to deploy your application, you must allow Django '
             'Deploy to access your Google account.').format(step_prompt))
        auth_client = auth.AuthClient()
        create_new_credentials = True
        active_account = auth_client.get_active_account()

        if active_account:  # The user has already logged in before
            while True:
                ans = console.ask(
                    ('You have logged in with account [{}]. Do you want to '
                     'use it? [Y/n]: ').format(active_account))
                ans = ans.lower()
                if ans not in ['y', 'n', '']:
                    continue
                elif ans in ['y', '']:
                    create_new_credentials = False
                break
        if not create_new_credentials:
            cred = auth_client.get_default_credentials()
            if cred:
                return cred
        return auth_client.create_default_credentials()


class BillingPrompt(Prompt):
    """Allow the user to select a billing account to use for deployment."""

    @staticmethod
    def _get_new_billing_account(
            console: io.IO, existing_billing_accounts: List[Dict[str, Any]],
            billing_client: billing.BillingClient) -> str:
        """Ask the user to create a new billing account and return name of it.

        Args:
            console: Object to use for user I/O.
            existing_billing_accounts: User's billing accounts before creation
                of new accounts.
            billing_client: A client to query user's existing billing accounts.

        Returns:
            Name of the user's newly created billing account.
        """
        webbrowser.open('https://console.cloud.google.com/billing/create')
        existing_billing_account_names = [
            account['name'] for account in existing_billing_accounts
        ]
        console.tell('Waiting for billing account to be created.')
        while True:
            billing_accounts = billing_client.list_billing_accounts(
                only_open_accounts=True)
            if len(existing_billing_accounts) != len(billing_accounts):
                billing_account_names = [
                    account['name'] for account in billing_accounts
                ]
                diff = list(
                    set(billing_account_names) -
                    set(existing_billing_account_names))
                return diff[0]
            time.sleep(2)

    @classmethod
    def prompt(cls,
               console: io.IO,
               step_prompt: str,
               arguments: Dict[str, Any],
               credentials: Optional[credentials.Credentials] = None) -> str:
        """Prompt the user for a billing account to use for deployment.

        Args:
            console: Object to use for user I/O.
            step_prompt: A prefix showing the current step number e.g. "[1/3]".
            arguments: The arguments that have already been collected from the
                user e.g. {"project_id", "project-123"}
            credentials: The OAuth2 Credentials object to use for api calls
                during prompt.

        Returns:
            The user's billing account name.
        """
        billing_client = billing.BillingClient.from_credentials(credentials)

        if ('project_creation_mode' in arguments and
            (arguments['project_creation_mode'] ==
             workflow.ProjectCreationMode.MUST_EXIST)):

            assert 'project_id' in arguments, 'project_id must be set'
            project_id = arguments['project_id']
            billing_account = (billing_client.get_billing_account(project_id))
            if billing_account.get('billingEnabled', False):
                msg = ('{} Billing is already enabled on this project.'.format(
                    step_prompt))
                console.tell(msg)
                return billing_account.get('billingAccountName')

        billing_accounts = billing_client.list_billing_accounts(
            only_open_accounts=True)
        console.tell(
            ('{} In order to deploy your application, you must enable billing '
             'for your Google Cloud Project.').format(step_prompt))

        # If the user has existing billing accounts, we let the user pick one
        if billing_accounts:
            console.tell('You have the following existing billing accounts: ')
            for i, account_info in enumerate(billing_accounts):
                console.tell('{}. {}'.format(i + 1,
                                             account_info['displayName']))
            choice = console.ask(
                ('Please enter your numeric choice or press [Enter] to create '
                 'a new billing account: '))
            while True:
                if not choice:
                    return cls._get_new_billing_account(
                        console, billing_accounts, billing_client)
                if (not choice.isdigit() or int(choice) <= 0 or
                        int(choice) > len(billing_accounts)):
                    if len(billing_accounts) == 1:
                        choice = console.ask(
                            ('Please enter "1" to use "{}" or press '
                             '[Enter] to create a new account: ').format(
                                 billing_accounts[0]['displayName']))
                    else:
                        choice = console.ask(
                            ('Please enter a value between 1 and {} or press '
                             '[Enter] to create a new account: ').format(
                                 len(billing_accounts)))
                else:
                    return billing_accounts[int(choice) - 1]['name']
        else:
            # If the user does not have existing billing accounts, we direct
            # the user to create a new one.
            console.tell('You do not have existing billing accounts.')
            console.ask('Press [Enter] to create a new billing account.')
            return cls._get_new_billing_account(console, billing_accounts,
                                                billing_client)

    @staticmethod
    def validate(s, credentials: Optional[credentials.Credentials] = None):
        """Validates that a string is a valid billing account.

        Args:
            s: The string to validate.
            credentials: The OAuth2 Credentials object to use for api calls
                during validation.

        Raises:
            ValueError: if the input string is not valid.
        """
        billing_client = billing.BillingClient(credentials)
        billing_accounts = billing_client.list_billing_accounts()
        billing_account_names = [
            account['name'] for account in billing_accounts
        ]
        if s not in billing_account_names:
            raise ValueError('The provided billing account does not exist.')
