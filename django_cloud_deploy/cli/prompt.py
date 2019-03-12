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
"""Prompts the user for information e.g. project name."""

import abc
import copy
import enum
import functools
import os.path
import random
import re
import string
import time
from typing import Any, Callable, Dict, List, Optional
import webbrowser

from django_cloud_deploy import workflow
from django_cloud_deploy.cli import io
from django_cloud_deploy.cloudlib import auth
from django_cloud_deploy.cloudlib import billing
from django_cloud_deploy.cloudlib import project
from django_cloud_deploy.skeleton import utils


class Command(enum.Enum):
    NEW = 1
    UPDATE = 2
    CLOUDIFY = 3


def _ask_prompt(question: str,
                console: io.IO,
                validate: Optional[Callable[[str], None]] = None,
                default: Optional[str] = None) -> str:
    """Used to ask for a single string value.

    Args:
        question: Question shown to the user on the console.
        console: Object to use for user I/O.
        validate: Function used to check if value provided is valid. It should
            raise a ValueError if the the value fails to validate.
        default: Default value if user provides no value. (Presses enter) If
            default is None, the user must provide an answer that is valid.

    Returns:
        The value entered by the user.
    """
    validate = validate or (lambda x: None)
    while True:
        answer = console.ask(question)
        if default and not answer:
            answer = default
        try:
            validate(answer)
            break
        except ValueError as e:
            console.error(e)

    return answer


def _multiple_choice_prompt(question: str,
                            options: List[str],
                            console: io.IO,
                            default: Optional[int] = None) -> Optional[int]:
    """Used to prompt user to choose from a list of values.

    Args:
        question: Question shown to the user on the console. Should have
            a {} to insert a list of enumerated options.
        options: Possible values user should choose from.
        console: Object to use for user I/O.
        default: Default value if user provides no value. (Presses enter) If
            default is None the user is forced to choose a value in the
            option list.

    Typical usage:
        # User can press enter if user doesn't want anything.
        choice = _multiple_choice_prompt('Choose an option:\n{}\n',
                                         ['Chicken', 'Salad', 'Burger'],
                                         console,
                                         default=None)

    Returns:
        The choice made by the user. If default is none, it is guaranteed to be
        an index in the options, else it can possible be the default value.
    """
    assert '{}' in question
    assert len(options) > 0

    options_formatted = [
        '{}. {}'.format(str(i), opt) for i, opt in enumerate(options, 1)
    ]
    options = '\n'.join(options_formatted)

    while True:
        answer = console.ask(question.format(options))

        if not answer and default:
            return default

        try:
            _multiple_choice_validate(answer, len(options))
            break
        except ValueError as e:
            console.error(e)

    return int(answer) - 1


def _multiple_choice_validate(s: str, len_options: int):
    """Validates the option chosen is valid.

    Args:
        s: Value to validate.
        len_options: Number of possible options for the user.

    Raises:
        ValueError: If the answer is not valid.
    """
    if not s:
        raise ValueError('Please enter a value between {} and {}'.format(
            1, len_options + 1))

    if not str.isnumeric(s):
        raise ValueError('Please enter a numeric value')

    if 1 <= int(s) <= (len_options + 1):
        return
    else:
        raise ValueError('Please enter a value between {} and {}'.format(
            1, len_options + 1))


def _binary_prompt(question: str,
                   console: io.IO,
                   default: Optional[bool] = None) -> bool:
    """Used to prompt user to choose from a yes or no question.

    Args:
        question: Question shown to the user on the console.
        console: Object to use for user I/O.
        default: Default value if user provides no value. (Presses enter) If
            default is None the user is forced to choose a value (y/n).

    Returns:
        The bool representation of the choice of the user. Yes is True.
    """

    while True:
        answer = console.ask(question).lower()

        if default is not None and not answer:
            return default

        try:
            _binary_validate(answer)
            break
        except ValueError as e:
            console.error(e)

    return answer == 'y'


def _binary_validate(s: str):
    """Ensures value is yes or no.

    Args:
        s: Value to validate.
    """
    if s.lower() not in ['y', 'n']:
        raise ValueError('Please respond using "y" or "n"')

    return


def _password_prompt(question: str, console: io.IO) -> str:
    """Used to prompt user to choose a password field.

    Args:
        console: Object to use for user I/O.
        question: Question shown to the user on the console.

    Returns:
        The password provided by the user.
    """
    console.tell(question)
    while True:
        password1 = console.getpass('Password: ')
        try:
            _password_validate(password1)
        except ValueError as e:
            console.error(e)
            continue
        password2 = console.getpass('Password (again): ')
        if password1 != password2:
            console.error('Passwords do not match, please try again')
            continue
        return password1


def _password_validate(s):
    """Validates that a string is a valid password.

    Args:
        s: The string to validate.

    Raises:
        ValueError: if the input string is not valid.
    """
    if len(s) < 6:
        raise ValueError('Passwords must be at least 6 characters long')
    allowed_characters = frozenset(string.ascii_letters + string.digits +
                                   string.punctuation)
    if frozenset(s).issuperset(allowed_characters):
        raise ValueError('Invalid character in password: '
                         'use letters, numbers and punctuation')

    return


class Prompt(abc.ABC):

    @abc.abstractmethod
    def prompt(self, console: io.IO, step: str,
               args: Dict[str, Any]) -> Dict[str, Any]:
        """Prompts the user if the required argument isn't already present.

        Args:
            console: Object to use for user I/O.
            step: Message to present to user regarding what step they are on.
                e.g. "[1 of 12]"
            args: Dictionary holding the results of previous prompts and
                command-line arguments.

        Returns:
            A copy of args plus new argument provided by this prompt.
        """
        pass

    @abc.abstractmethod
    def _is_valid_passed_arg(self, console: io.IO, step: str,
                             value: Optional[str],
                             validate: Callable[[str], None]) -> bool:
        """Used to validate if the user passed in a parameter as a flag.

        All prompts that retrieve a parameter should call this function first.
        This allows for passed in paramters via flags be considered as a step.
        This is used to have a hard coded amount of steps that is easier to
        manage.

        Returns:
            A boolean indicating if the passed in argument is valid.
        """
        pass


class TemplatePrompt(Prompt):
    """Base template for all parameter prompts interacting with the user.

    They must have a prompt method that calls one of the _x_prompt functions.
    They must own only one parameter.
    They should have a validate function.
    They should call _is_valid_passed_arg at the beggining of prompt method.
    """

    # Parameter must be set for dictionary key
    PARAMETER = None

    def prompt(self, console: io.IO, step: str,
               args: Dict[str, Any]) -> Dict[str, Any]:
        """Extracts user arguments through the command-line.

        Args:
            console: Object to use for user I/O.
            step: Message to present to user regarding what step they are on.
            args: Dictionary holding prompts answered by user and set up
                command-line arguments.

        Returns: A Copy of args + the new parameter collected.
        """
        pass

    def _is_valid_passed_arg(self, console: io.IO, step: str,
                             value: Optional[str],
                             validate: Callable[[str], None]) -> bool:
        """Checks if the passed in argument via the command line is valid.

        All prompts that collect a parameter should call this function first.
        It uses the validate function of the prompt. The code also
        will process a passed in paramater as a step. This is used to have a
        static amount of steps that is easier to manage.

        Returns:
            A boolean indicating if the passed in argument is valid.
        """
        if value is None:
            return False

        try:
            validate(value)
        except ValueError as e:
            console.error(e)
            quit()

        msg = '{} {}: {}'.format(step, self.PARAMETER, value)
        console.tell(msg)
        return True


class StringTemplatePrompt(TemplatePrompt):
    """Template for a simple string Prompt.

    Any prompt that only needs to ask the user for a value without additional
    branching or logic should derive from this class. Classes inheriting from
    this should set the variables below.
    """

    # The key used for the args dictionary, eg. project_id
    PARAMETER = ''
    # Value user can use if they press enter on the command line, eg django-1234
    DEFAULT_VALUE = ''
    # Message to prompt the user on the command-line, eg. Please choose a
    # project id.
    MESSAGE = ''

    def prompt(self, console: io.IO, step: str,
               args: Dict[str, Any]) -> Dict[str, Any]:
        """Extracts user arguments through the command-line.

        Args:
            console: Object to use for user I/O.
            step: Message to present to user regarding what step they are on.
            args: Dictionary holding prompts answered by user and set up
                command-line arguments.

        Returns: A Copy of args + the new parameter collected.
        """
        new_args = copy.deepcopy(args)
        if self._is_valid_passed_arg(console, step,
                                     args.get(self.PARAMETER, None),
                                     self._validate):
            return new_args

        base_message = self.MESSAGE.format(step)
        default_message = '[{}]: '.format(self.DEFAULT_VALUE)
        msg = '\n'.join([base_message, default_message])
        answer = _ask_prompt(
            msg, console, self._validate, default=self.DEFAULT_VALUE)
        new_args[self.PARAMETER] = answer
        return new_args


class GoogleProjectName(TemplatePrompt):

    PARAMETER = 'project_name'

    def __init__(self, project_client: project.ProjectClient):
        self.project_client = project_client

    def _validate(self, project_id: str,
                  project_creation_mode: workflow.ProjectCreationMode, s: str):
        """Returns the method that validates the string.

        Args:
            project_id: Used to retrieve name when project already exists.
            project_creation_mode: Used to check if project already exists.
            s: The string to validate
        """
        if not (4 <= len(s) <= 30):
            raise ValueError(
                ('Invalid Google Cloud Platform project name "{}": '
                 'must be between 4 and 30 characters').format(s))

        if self._is_new_project(project_creation_mode):
            return

        assert project_id is not None

        project_name = self.project_client.get_project(project_id)['name']
        if project_name != s:
            raise ValueError('Wrong project name given for project id.')

    def _handle_new_project(self, console: io.IO, step: str, args: [str, Any]):
        default_answer = 'Django Project'
        msg_base = ('{} Enter a Google Cloud Platform project name, or leave '
                    'blank to use').format(step)
        msg_default = '[{}]: '.format(default_answer)
        msg = '\n'.join([msg_base, msg_default])
        project_id = args.get('project_id', None)
        mode = args.get('project_creation_mode', None)
        validate = functools.partial(self._validate, project_id, mode)
        return _ask_prompt(msg, console, validate, default=default_answer)

    def _is_new_project(
            self, project_creation_mode: workflow.ProjectCreationMode) -> bool:
        must_exist = workflow.ProjectCreationMode.MUST_EXIST
        return project_creation_mode != must_exist

    def _handle_existing_project(self, console: io.IO, step: str,
                                 args: Dict[str, Any]) -> str:
        assert 'project_id' in args, 'project_id must be set'
        project_id = args['project_id']
        project_name = self.project_client.get_project(project_id)['name']
        message = '{} {}: {}'.format(step, self.PARAMETER, project_name)
        console.tell(message)
        return project_name

    def prompt(self, console: io.IO, step: str,
               args: Dict[str, Any]) -> Dict[str, Any]:
        """Extracts user arguments through the command-line.

        Args:
            console: Object to use for user I/O.
            step: Message to present to user regarding what step they are on.
            args: Dictionary holding prompts answered by user and set up
                command-line arguments.

        Returns: A Copy of args + the new parameter collected.
        """
        new_args = copy.deepcopy(args)

        project_id = args.get('project_id', None)
        mode = args.get('project_creation_mode', None)
        validate = functools.partial(self._validate, project_id, mode)
        if self._is_valid_passed_arg(console, step,
                                     args.get(self.PARAMETER, None), validate):
            return new_args

        project_creation_mode = args.get('project_creation_mode', None)
        if self._is_new_project(project_creation_mode):
            new_args[self.PARAMETER] = self._handle_new_project(
                console, step, args)
        else:
            new_args[self.PARAMETER] = self._handle_existing_project(
                console, step, args)

        return new_args


class GoogleNewProjectId(TemplatePrompt):
    """Handles Project ID for new projects."""

    PARAMETER = 'project_id'

    def _validate(self, s: str):
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

    def _generate_default_project_id(self, project_name=None):
        default_project_id = (project_name or 'django').lower()
        default_project_id = default_project_id.replace(' ', '-')
        if default_project_id[0] not in string.ascii_lowercase:
            default_project_id = 'django-' + default_project_id
        default_project_id = re.sub(r'[^a-z0-9\-]', '', default_project_id)

        return '{0}-{1}'.format(default_project_id[0:30 - 6 - 1],
                                random.randint(100000, 1000000))

    def prompt(self, console: io.IO, step: str,
               args: Dict[str, Any]) -> Dict[str, Any]:
        """Extracts user arguments through the command-line.

        Args:
            console: Object to use for user I/O.
            step: Message to present to user regarding what step they are on.
            args: Dictionary holding prompts answered by user and set up
                command-line arguments.

        Returns: A Copy of args + the new parameter collected.
        """
        new_args = copy.deepcopy(args)
        if self._is_valid_passed_arg(console, step,
                                     args.get(self.PARAMETER, None),
                                     self._validate):
            return new_args

        project_name = args.get('project_name', None)
        default_answer = self._generate_default_project_id(project_name)
        msg_base = ('{} Enter a Google Cloud Platform Project ID, '
                    'or leave blank to use').format(step)
        msg_default = '[{}]: '.format(default_answer)
        msg = '\n'.join([msg_base, msg_default])
        answer = _ask_prompt(
            msg, console, self._validate, default=default_answer)
        new_args[self.PARAMETER] = answer
        return new_args


class GoogleProjectId(TemplatePrompt):
    """Logic that handles fork between Existing and New Projects."""

    PARAMETER = 'project_id'

    def __init__(self, project_client: project.ProjectClient):
        self.project_client = project_client

    def prompt(self, console: io.IO, step: str,
               args: Dict[str, Any]) -> Dict[str, Any]:
        """Extracts user arguments through the command-line.

        Args:
            console: Object to use for user I/O.
            step: Message to present to user regarding what step they are on.
            args: Dictionary holding prompts answered by user and set up
                command-line arguments.

        Returns: A Copy of args + the new parameter collected.
        """
        prompter = GoogleNewProjectId()

        if args.get('use_existing_project', False):
            prompter = GoogleExistingProjectId(self.project_client)

        return prompter.prompt(console, step, args)


class GoogleExistingProjectId(TemplatePrompt):
    """Handles Project ID for existing projects."""

    PARAMETER = 'project_id'

    def __init__(self, project_client: project.ProjectClient):
        self.project_client = project_client

    def prompt(self, console: io.IO, step: str,
               args: Dict[str, Any]) -> Dict[str, Any]:
        """Extracts user arguments through the command-line.

        Args:
            console: Object to use for user I/O.
            step: Message to present to user regarding what step they are on.
            args: Dictionary holding prompts answered by user and set up
                command-line arguments.

        Returns: A Copy of args + the new parameter collected.
        """

        new_args = copy.deepcopy(args)
        if self._is_valid_passed_arg(console, step, args.get(self.PARAMETER),
                                     self._validate):
            return new_args

        msg = ('{} Enter the <b>existing</b> Google Cloud Platform Project ID '
               'to use.').format(step)
        answer = _ask_prompt(msg, console, self._validate)
        new_args[self.PARAMETER] = answer
        return new_args

    def _validate(self, s: str):
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

        if not self.project_client.project_exists(s):
            raise ValueError('Project {} does not exist'.format(s))


class CredentialsPrompt(TemplatePrompt):

    PARAMETER = 'credentials'

    def __init__(self, auth_client: auth.AuthClient):
        self.auth_client = auth_client

    def prompt(self, console: io.IO, step: str,
               args: Dict[str, Any]) -> Dict[str, Any]:
        """Extracts user arguments through the command-line.

        Args:
            console: Object to use for user I/O.
            step: Message to present to user regarding what step they are on.
            args: Dictionary holding prompts answered by user and set up
                command-line arguments.

        Returns: A Copy of args + the new parameter collected.
        """
        new_args = copy.deepcopy(args)
        if self._is_valid_passed_arg(console, step,
                                     args.get(self.PARAMETER), lambda x: x):
            return new_args

        console.tell(
            ('{} In order to deploy your application, you must allow Django '
             'Deploy to access your Google account.').format(step))
        create_new_credentials = True
        active_account = self.auth_client.get_active_account()

        if active_account:  # The user has already logged in before
            msg = ('You have logged in with account [{}]. Do you want to '
                   'use it? [Y/n]: ').format(active_account)
            use_active_credentials = _binary_prompt(msg, console, default='Y')
            create_new_credentials = not use_active_credentials

        if create_new_credentials:
            creds = self.auth_client.create_default_credentials()
        else:
            creds = self.auth_client.get_default_credentials()

        new_args[self.PARAMETER] = creds
        return new_args


class BillingPrompt(TemplatePrompt):
    """Allow the user to select a billing account to use for deployment."""

    PARAMETER = 'billing_account_name'

    def __init__(self, billing_client: billing.BillingClient = None):
        self.billing_client = billing_client

    def _get_new_billing_account(
            self, console,
            existing_billing_accounts: List[Dict[str, Any]]) -> str:
        """Ask the user to create a new billing account and return name of it.

        Args:
            existing_billing_accounts: User's billing accounts before creation
                of new accounts.

        Returns:
            Name of the user's newly created billing account.
        """
        webbrowser.open('https://console.cloud.google.com/billing/create')
        existing_billing_account_names = [
            account['name'] for account in existing_billing_accounts
        ]
        console.tell('Waiting for billing account to be created.')
        while True:
            billing_accounts = self.billing_client.list_billing_accounts(
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

    def _does_project_exist(
            self, project_creation_mode: Optional[workflow.ProjectCreationMode]
    ) -> bool:
        must_exist = workflow.ProjectCreationMode.MUST_EXIST
        return project_creation_mode == must_exist

    def _has_existing_billing_account(self, console: io.IO, step: str,
                                      args: Dict[str, Any]) -> (Optional[str]):
        assert 'project_id' in args, 'project_id must be set'
        project_id = args['project_id']
        billing_account = (self.billing_client.get_billing_account(project_id))
        if not billing_account.get('billingEnabled', False):
            return None

        msg = ('{} Billing is already enabled on this project.'.format(step))
        console.tell(msg)
        return billing_account.get('billingAccountName')

    def _handle_existing_billing_accounts(self, console, billing_accounts):
        question = ('You have the following existing billing accounts:\n{}\n'
                    'Please enter your numeric choice or press [Enter] to '
                    'create a new billing account: ')

        options = [info['displayName'] for info in billing_accounts]

        new_billing_account = -1
        answer = _multiple_choice_prompt(question, options, console,
                                         new_billing_account)

        if answer == new_billing_account:
            return self._get_new_billing_account(console, billing_accounts)

        val = billing_accounts[answer]['name']
        return val

    def prompt(self, console: io.IO, step: str,
               args: Dict[str, Any]) -> Dict[str, Any]:
        """Extracts user arguments through the command-line.

        Args:
            console: Object to use for user I/O.
            step: Message to present to user regarding what step they are on.
            args: Dictionary holding prompts answered by user and set up
                command-line arguments.

        Returns: A Copy of args + the new parameter collected.
        """
        new_args = copy.deepcopy(args)
        if self._is_valid_passed_arg(console, step, args.get(self.PARAMETER),
                                     self._validate):
            return new_args

        project_creation_mode = args.get('project_creation_mode')
        if self._does_project_exist(project_creation_mode):
            billing_account = self._has_existing_billing_account(
                console, step, args)
            if billing_account is not None:
                new_args[self.PARAMETER] = billing_account
                return new_args

        billing_accounts = self.billing_client.list_billing_accounts(
            only_open_accounts=True)
        console.tell(
            ('{} In order to deploy your application, you must enable billing '
             'for your Google Cloud Project.').format(step))

        # If the user has existing billing accounts, we let the user pick one
        if billing_accounts:
            val = self._handle_existing_billing_accounts(
                console, billing_accounts)
            new_args[self.PARAMETER] = val
            return new_args

        # If the user does not have existing billing accounts, we direct
        # the user to create a new one.
        console.tell('You do not have existing billing accounts.')
        console.ask('Press [Enter] to create a new billing account.')
        val = self._get_new_billing_account(console, billing_accounts)
        new_args[self.PARAMETER] = val
        return new_args

    def _validate(self, s):
        """Validates that a string is a valid billing account.

        Args:
            s: The string to validate.

        Raises:
            ValueError: if the input string is not valid.
        """

        billing_accounts = self.billing_client.list_billing_accounts()
        billing_account_names = [
            account['name'] for account in billing_accounts
        ]
        if s not in billing_account_names:
            raise ValueError('The provided billing account does not exist.')


class PostgresPasswordPrompt(TemplatePrompt):
    """Allow the user to enter a Django Postgres password."""

    PARAMETER = 'database_password'

    def prompt(self, console: io.IO, step: str,
               args: Dict[str, Any]) -> Dict[str, Any]:
        """Extracts user arguments through the command-line.

        Args:
            console: Object to use for user I/O.
            step: Message to present to user regarding what step they are on.
            args: Dictionary holding prompts answered by user and set up
                command-line arguments.

        Returns: A Copy of args + the new parameter collected.
        """
        new_args = copy.deepcopy(args)
        if self._is_valid_passed_arg(console, step, args.get(self.PARAMETER),
                                     self._validate):
            return new_args

        msg = 'Enter a password for the default database user "postgres"'
        question = '{} {}'.format(step, msg)
        password = _password_prompt(question, console)
        new_args[self.PARAMETER] = password
        return new_args

    def _validate(self, s: str):
        _password_validate(s)


class DjangoFilesystemPath(TemplatePrompt):
    """Allow the user to indicate the file system path for their project."""

    PARAMETER = 'django_directory_path'

    def _ask_to_replace(self, console, directory):
        msg = (('The directory \'{}\' already exists, '
                'replace it\'s contents [y/N]: ').format(directory))
        return _ask_prompt(msg, console, default='n')

    def _ask_for_directory(self, console, step, args) -> str:
        base_msg = ('{} Enter a new directory path to store project source, '
                    'or leave blank to use').format(step)

        home_dir = os.path.expanduser('~')
        # TODO: Remove filesystem-unsafe characters. Implement a validation
        # method that checks for these.
        default_dir = os.path.join(
            home_dir,
            args.get('project_name', 'django-project').lower().replace(
                ' ', '-'))
        default_msg = '[{}]: '.format(default_dir)

        msg = '\n'.join([base_msg, default_msg])
        return _ask_prompt(msg, console, default=default_dir)

    def prompt(self, console: io.IO, step: str,
               args: Dict[str, Any]) -> Dict[str, Any]:
        """Extracts user arguments through the command-line.

        Args:
            console: Object to use for user I/O.
            step: Message to present to user regarding what step they are on.
            args: Dictionary holding prompts answered by user and set up
                command-line arguments.

        Returns: A Copy of args + the new parameter collected.
        """
        new_args = copy.deepcopy(args)

        if self._is_valid_passed_arg(console, step,
                                     args.get(self.PARAMETER), lambda x: x):
            return new_args

        while True:
            directory = self._ask_for_directory(console, step, args)
            if os.path.exists(directory):
                replace = self._ask_to_replace(console, directory)
                if replace.lower() == 'n':
                    continue
            break

        new_args[self.PARAMETER] = directory
        return new_args


class DjangoFilesystemPathUpdate(TemplatePrompt):
    """Allow the user to indicate the file system path for their project."""

    PARAMETER = 'django_directory_path_update'

    def _ask_for_directory(self, console, step, args) -> str:
        base_msg = ('{} Enter the django project directory path '
                    'or leave blank to use').format(step)

        home_dir = os.path.expanduser('~')
        # TODO: Remove filesystem-unsafe characters. Implement a validation
        # method that checks for these.
        default_dir = os.path.join(
            home_dir,
            args.get('project_name', 'django-project').lower().replace(
                ' ', '-'))
        default_msg = '[{}]: '.format(default_dir)

        msg = '\n'.join([base_msg, default_msg])
        return _ask_prompt(msg, console, default=default_dir)

    def prompt(self, console: io.IO, step: str,
               args: Dict[str, Any]) -> Dict[str, Any]:
        """Extracts user arguments through the command-line.

        Args:
            console: Object to use for user I/O.
            step: Message to present to user regarding what step they are on.
            args: Dictionary holding prompts answered by user and set up
                command-line arguments.

        Returns: A Copy of args + the new parameter collected.
        """
        new_args = copy.deepcopy(args)
        if self._is_valid_passed_arg(console, step, args.get(self.PARAMETER),
                                     self._validate):
            return new_args

        while True:
            directory = self._ask_for_directory(console, step, args)
            try:
                self._validate(directory)
            except ValueError as e:
                console.error(e)
                continue
            break

        new_args[self.PARAMETER] = directory
        return new_args

    def _validate(self, s: str):
        """Validates that a string is a valid Django project path.

        Args:
            s: The string to validate.

        Raises:
            ValueError: if the input string is not valid.
        """
        if not os.path.exists(s):
            raise ValueError(('Path ["{}"] does not exist.').format(s))

        if not utils.is_valid_django_project(s):
            raise ValueError(
                ('Path ["{}"] does not contain a valid Django project.'
                ).format(s))


class DjangoFilesystemPathCloudify(StringTemplatePrompt):
    """Allow the user to indicate the file system path for their project."""

    PARAMETER = 'django_directory_path_cloudify'
    MESSAGE = ('{} Enter the directory of the Django project you want to '
               'deploy: ')

    def _validate(self, s: str):
        """Validates that a string is a valid Django project path.

        Args:
            s: The string to validate.

        Raises:
            ValueError: if the input string is not valid.
        """
        if not os.path.exists(s):
            raise ValueError(('Path ["{}"] does not exist.').format(s))

        if not utils.is_valid_django_project(s):
            raise ValueError(
                ('Path ["{}"] does not contain a valid Django project.'
                ).format(s))


class DjangoProjectNamePrompt(StringTemplatePrompt):
    """Allow the user to enter a Django project name."""

    PARAMETER = 'django_project_name'
    MESSAGE = '{} Enter a Django project name or leave blank to use'
    DEFAULT_VALUE = 'mysite'

    def _validate(self, s: str):
        """Validates that a string is a valid Django project name.

        Args:
            s: The string to validate.

        Raises:
            ValueError: if the input string is not valid.
        """
        if not s.isidentifier():
            raise ValueError(('Invalid Django project name "{}": '
                              'must be a valid Python identifier').format(s))


class DjangoAppNamePrompt(StringTemplatePrompt):
    """Allow the user to enter a Django project name."""

    PARAMETER = 'django_app_name'
    MESSAGE = '{} Enter a Django app name or leave blank to use'
    DEFAULT_VALUE = 'home'

    def _validate(self, s: str):
        """Validates that a string is a valid Django project name.

        Args:
            s: The string to validate.

        Raises:
            ValueError: if the input string is not valid.
        """
        if not s.isidentifier():
            raise ValueError(('Invalid Django project name "{}": '
                              'must be a valid Python identifier').format(s))


class DjangoSuperuserLoginPrompt(StringTemplatePrompt):
    """Allow the user to enter a Django superuser login."""

    PARAMETER = 'django_superuser_login'
    MESSAGE = '{} Enter a Django superuser login name or leave blank to use'
    DEFAULT_VALUE = 'admin'

    def _validate(self, s: str):
        """Validates that a string is a valid Django superuser login.

        Args:
            s: The string to validate.

        Raises:
            ValueError: if the input string is not valid.
        """
        if not s.isalnum():
            raise ValueError(('Invalid Django superuser login "{}": '
                              'must be a alpha numeric').format(s))


class DjangoSuperuserPasswordPrompt(TemplatePrompt):
    """Allow the user to enter a password for the Django superuser."""

    PARAMETER = 'django_superuser_password'

    def _get_prompt_message(self, arguments: Dict[str, Any]) -> str:
        if 'django_superuser_login' in arguments:
            return 'Enter a password for the Django superuser "{}"'.format(
                arguments['django_superuser_login'])
        else:
            return 'Enter a password for the Django superuser'

    def prompt(self, console: io.IO, step: str,
               args: Dict[str, Any]) -> Dict[str, Any]:
        """Extracts user arguments through the command-line.

        Args:
            console: Object to use for user I/O.
            step: Message to present to user regarding what step they are on.
            args: Dictionary holding prompts answered by user and set up
                command-line arguments.

        Returns: A Copy of args + the new parameter collected.
        """
        new_args = copy.deepcopy(args)
        if self._is_valid_passed_arg(console, step, args.get(self.PARAMETER),
                                     self._validate):
            return new_args

        msg = self._get_prompt_message(args)
        question = '{} {}'.format(step, msg)
        answer = _password_prompt(question, console)
        new_args[self.PARAMETER] = answer
        return new_args

    def _validate(self, s: str):
        return _password_validate(s)


class DjangoSuperuserEmailPrompt(StringTemplatePrompt):
    """Allow the user to enter a Django email address."""

    PARAMETER = 'django_superuser_email'
    MESSAGE = ('{} Enter an email adress for the Django superuser '
               'or leave blank to use')
    DEFAULT_VALUE = 'test@example.com'

    def _validate(self, s: str):
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


class RootPrompt(object):
    """Class at the top level that instantiates all of the Prompts."""

    NEW_PROMPT_ORDER = [
        'project_id',
        'project_name',
        'billing_account_name',
        'database_password',
        'django_directory_path',
        'django_project_name',
        'django_app_name',
        'django_superuser_login',
        'django_superuser_password',
        'django_superuser_email',
    ]

    UPDATE_PROMPT_ORDER = [
        'database_password',
        'django_directory_path_update',
    ]

    CLOUDIFY_PROMPT_ORDER = [
        'project_id',
        'project_name',
        'billing_account_name',
        'database_password',
        'django_directory_path_cloudify',
        'django_superuser_login',
        'django_superuser_password',
        'django_superuser_email',
    ]

    def _get_creds(self, console: io.IO, first_step: str, args: Dict[str, Any]):
        auth_client = auth.AuthClient()
        return CredentialsPrompt(auth_client).prompt(console, first_step,
                                                     args)['credentials']

    def _setup_prompts(self, creds) -> Dict[str, TemplatePrompt]:
        project_client = project.ProjectClient.from_credentials(creds)
        billing_client = billing.BillingClient.from_credentials(creds)

        return {
            'project_id': GoogleProjectId(project_client),
            'project_name': GoogleProjectName(project_client),
            'billing_account_name': BillingPrompt(billing_client),
            'database_password': PostgresPasswordPrompt(),
            'django_directory_path': DjangoFilesystemPath(),
            'django_directory_path_update': DjangoFilesystemPathUpdate(),
            'django_directory_path_cloudify': DjangoFilesystemPathCloudify(),
            'django_project_name': DjangoProjectNamePrompt(),
            'django_app_name': DjangoAppNamePrompt(),
            'django_superuser_login': DjangoSuperuserLoginPrompt(),
            'django_superuser_password': DjangoSuperuserPasswordPrompt(),
            'django_superuser_email': DjangoSuperuserEmailPrompt()
        }

    def prompt(self, command: Command, console: io.IO,
               args: Dict[str, Any]) -> Dict[str, Any]:
        """Calls all of the prompts to collect all of the paramters.

        Args:
            command: Flag that picks what prompts are needed.
            console: Object to use for user I/O.
            args: Dictionary holding prompts answered by user and set up
                command-line arguments.

        Returns: A Copy of args + the new parameter collected.
        """
        new_args = copy.deepcopy(args)
        if new_args.get('use_existing_project', False):
            new_args['project_creation_mode'] = (
                workflow.ProjectCreationMode.MUST_EXIST)

        prompt_order = []
        if command == Command.NEW:
            prompt_order = self.NEW_PROMPT_ORDER
        elif command == Command.UPDATE:
            prompt_order = self.UPDATE_PROMPT_ORDER
        elif command == Command.CLOUDIFY:
            prompt_order = self.CLOUDIFY_PROMPT_ORDER

        total_steps = len(prompt_order) + 1
        step_template = '<b>[{}/{}]</b>'
        first_step = step_template.format(1, total_steps)

        creds = self._get_creds(console, first_step, args)
        new_args['credentials'] = creds
        required_parameters_to_prompt = self._setup_prompts(creds)
        for i, prompt in enumerate(prompt_order, 2):
            step = step_template.format(i, total_steps)
            new_args = required_parameters_to_prompt[prompt].prompt(
                console, step, new_args)

        return new_args
