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
"""Tests for django_cloud_deploy.cli.prompt."""

import os
import shutil
import sys
import tempfile
from unittest import mock

from absl.testing import absltest
from absl.testing import parameterized

from django.core import management

from django_cloud_deploy import workflow
from django_cloud_deploy.cli import io
from django_cloud_deploy.cli import prompt
from django_cloud_deploy.cloudlib import billing
from django_cloud_deploy.cloudlib import project

from google.auth import credentials

_FAKE_PROJECT_RESPONSE = {
    "projectNumber": "814717604088",
    "projectId": "project-abc",
    "lifecycleState": "ACTIVE",
    "name": "Djangogke Project",
    "createTime": "2018-09-25T00:18:30.394Z",
    "parent": {
        "type": "organization",
        "id": "433637338589"
    }
}

_FAKE_PERMISSIONS_RESPONSE_OWNER = [{
    'role': 'roles/owner',
    'members': ['user:email@email.com']
}]

_FAKE_PERMISSIONS_RESPONSE_EDITOR = [{
    'role': 'roles/editor',
    'members': ['user:email@email.com']
}]


class GoogleCloudProjectNamePromptTest(absltest.TestCase):
    """Tests for prompt.GoogleCloudProjectNamePrompt."""

    @classmethod
    def setUpClass(cls):
        creds = mock.Mock(credentials.Credentials, authSpec=True)
        project_client = project.ProjectClient.from_credentials(creds)

        cls.google_project_name_prompt = prompt.GoogleProjectName(
            project_client)

    def test_prompt(self):
        test_io = io.TestIO()

        test_io.answers.append('My Project')
        args = self.google_project_name_prompt.prompt(test_io, '[1/2]', {})
        name = args['project_name']
        self.assertEqual(name, 'My Project')
        self.assertEqual(len(test_io.answers), 0)  # All answers used.

    def test_prompt_default(self):
        test_io = io.TestIO()

        test_io.answers.append('')
        args = self.google_project_name_prompt.prompt(test_io, '[1/2]', {})
        name = args['project_name']
        self.assertEqual(name, 'Django Project')
        self.assertEqual(len(test_io.answers), 0)  # All answers used.

    def test_prompt_bad_name(self):
        test_io = io.TestIO()

        test_io.answers.append('S')
        test_io.answers.append('Long Enough')
        args = self.google_project_name_prompt.prompt(test_io, '[1/2]', {})
        name = args['project_name']
        self.assertEqual(name, 'Long Enough')
        self.assertEqual(len(test_io.answers), 0)  # All answers used.

    @mock.patch('django_cloud_deploy.cloudlib.project.ProjectClient.'
                'get_project',
                return_value=_FAKE_PROJECT_RESPONSE)
    def test_prompt_use_existing_project(self, unused_mock):
        test_io = io.TestIO()

        args = {
            'project_creation_mode': workflow.ProjectCreationMode.MUST_EXIST,
            'project_id': 'project-abc'
        }
        args = self.google_project_name_prompt.prompt(test_io, '[1/2]', args)
        name = args['project_name']
        self.assertEqual(name, _FAKE_PROJECT_RESPONSE['name'])


class DjangoProjectNamePromptTest(absltest.TestCase):
    """Tests for prompt.DjangoProjectNamePrompt."""

    @classmethod
    def setUpClass(cls):
        cls.djang_project_name_prompt = prompt.DjangoProjectNamePrompt()

    def test_prompt(self):
        test_io = io.TestIO()

        test_io.answers.append('djangoproject')
        args = self.djang_project_name_prompt.prompt(test_io, '[1/2]', {})
        name = args['django_project_name']
        self.assertEqual(name, 'djangoproject')
        self.assertEqual(len(test_io.answers), 0)  # All answers used.

    def test_prompt_default(self):
        test_io = io.TestIO()

        test_io.answers.append('')
        args = self.djang_project_name_prompt.prompt(test_io, '[1/2]', {})
        name = args['django_project_name']
        self.assertEqual(name, 'mysite')
        self.assertEqual(len(test_io.answers), 0)  # All answers used.

    def test_prompt_bad_name(self):
        test_io = io.TestIO()

        test_io.answers.append('5')
        test_io.answers.append('djangoproject')
        args = self.djang_project_name_prompt.prompt(test_io, '[1/2]', {})
        name = args['django_project_name']
        self.assertEqual(name, 'djangoproject')
        self.assertEqual(len(test_io.answers), 0)  # All answers used.


class DjangoAppNamePromptTest(absltest.TestCase):
    """Tests for prompt.DjangoAppNamePrompt."""

    @classmethod
    def setUpClass(cls):
        cls.django_app_name_prompt = prompt.DjangoAppNamePrompt()

    def test_prompt(self):
        test_io = io.TestIO()

        test_io.answers.append('djangoapp')
        args = self.django_app_name_prompt.prompt(test_io, '[1/2]', {})
        name = args['django_app_name']
        self.assertEqual(name, 'djangoapp')
        self.assertEqual(len(test_io.answers), 0)  # All answers used.

    def test_prompt_default(self):
        test_io = io.TestIO()

        test_io.answers.append('')
        args = self.django_app_name_prompt.prompt(test_io, '[1/2]', {})
        name = args['django_app_name']
        self.assertEqual(name, 'home')
        self.assertEqual(len(test_io.answers), 0)  # All answers used.

    def test_prompt_bad_name(self):
        test_io = io.TestIO()

        test_io.answers.append('5')
        test_io.answers.append('djangoapp')
        args = self.django_app_name_prompt.prompt(test_io, '[1/2]', {})
        name = args['django_app_name']
        self.assertEqual(name, 'djangoapp')
        self.assertEqual(len(test_io.answers), 0)  # All answers used.

    def test_prompt_same_name_as_project(self):
        test_io = io.TestIO()

        test_io.answers.append('djangoproject')
        test_io.answers.append('djangoapp')
        args = {'django_project_name': 'djangoproject'}
        args = self.django_app_name_prompt.prompt(test_io, '[1/2]', args)
        name = args['django_app_name']
        self.assertEqual(name, 'djangoapp')
        self.assertEqual(len(test_io.answers), 0)  # All answers used.


class DjangoSuperuserLoginPromptTest(absltest.TestCase):
    """Tests for prompt.DjangoSuperuserLoginPrompt."""

    @classmethod
    def setUpClass(cls):
        cls.django_superuser_prompt = prompt.DjangoSuperuserLoginPrompt()

    def test_prompt(self):
        test_io = io.TestIO()

        test_io.answers.append('myusername')
        args = self.django_superuser_prompt.prompt(test_io, '[1/2]', {})
        name = args['django_superuser_login']
        self.assertEqual(name, 'myusername')
        self.assertEqual(len(test_io.answers), 0)  # All answers used.

    def test_prompt_default(self):
        test_io = io.TestIO()

        test_io.answers.append('')
        args = self.django_superuser_prompt.prompt(test_io, '[1/2]', {})
        name = args['django_superuser_login']
        self.assertEqual(name, 'admin')
        self.assertEqual(len(test_io.answers), 0)  # All answers used.

    def test_prompt_bad_name(self):
        test_io = io.TestIO()

        test_io.answers.append('My Name')
        test_io.answers.append('myname')
        args = self.django_superuser_prompt.prompt(test_io, '[1/2]', {})
        name = args['django_superuser_login']
        self.assertEqual(name, 'myname')
        self.assertEqual(len(test_io.answers), 0)  # All answers used.


class DjangoSuperuserEmailPromptTest(absltest.TestCase):
    """Tests for prompt.DjangoSuperuserEmailPrompt."""

    @classmethod
    def setUpClass(cls):
        cls.django_superuser_email_prompt = prompt.DjangoSuperuserEmailPrompt()

    def test_prompt(self):
        test_io = io.TestIO()

        test_io.answers.append('admin@example.com')
        args = self.django_superuser_email_prompt.prompt(test_io, '[1/2]', {})
        email = args['django_superuser_email']
        self.assertEqual(email, 'admin@example.com')
        self.assertEqual(len(test_io.answers), 0)  # All answers used.

    def test_prompt_default(self):
        test_io = io.TestIO()

        test_io.answers.append('')
        args = self.django_superuser_email_prompt.prompt(test_io, '[1/2]', {})
        email = args['django_superuser_email']
        self.assertEqual(email, 'test@example.com')
        self.assertEqual(len(test_io.answers), 0)  # All answers used.

    def test_prompt_bad_address(self):
        test_io = io.TestIO()

        test_io.answers.append('Not An Email Address')
        test_io.answers.append('admin@example.com')
        args = self.django_superuser_email_prompt.prompt(test_io, '[1/2]', {})
        email = args['django_superuser_email']
        self.assertEqual(email, 'admin@example.com')
        self.assertEqual(len(test_io.answers), 0)  # All answers used.


class ProjectIdPromptTest(parameterized.TestCase):
    """Tests for prompt.ProjectIdPrompt."""

    @classmethod
    def setUpClass(cls):
        creds = mock.Mock(credentials.Credentials, authSpec=True)
        project_client = project.ProjectClient.from_credentials(creds)
        active_account = 'email@email.com'
        cls.project_id_prompt = prompt.GoogleProjectId(project_client,
                                                       active_account)

    def test_new_prompt(self):
        test_io = io.TestIO()
        args = {
            'project_creation_mode': workflow.ProjectCreationMode.CREATE,
        }
        test_io.answers.append('projectid-123')
        args = self.project_id_prompt.prompt(test_io, '[1/2]', args)
        project_id = args['project_id']

        self.assertEqual(project_id, 'projectid-123')
        self.assertEqual(len(test_io.answers), 0)  # All answers used.

    def test_prompt_default(self):
        test_io = io.TestIO()
        args = {
            'project_creation_mode': workflow.ProjectCreationMode.CREATE,
        }
        test_io.answers.append('')
        args = self.project_id_prompt.prompt(test_io, '[1/2]', args)
        project_id = args['project_id']
        self.assertRegex(project_id, r'django-\d{6}')
        self.assertEqual(len(test_io.answers), 0)  # All answers used.

    @mock.patch('django_cloud_deploy.cloudlib.project.ProjectClient.'
                'project_exists',
                return_value=True)
    @mock.patch('django_cloud_deploy.cloudlib.project.ProjectClient.'
                'get_project_permissions',
                return_value=_FAKE_PERMISSIONS_RESPONSE_OWNER)
    def test_existing_prompt(self, *unused_mock):
        test_io = io.TestIO()
        args = {
            'backend': 'gae',
            'project_creation_mode': workflow.ProjectCreationMode.MUST_EXIST,
            'project_id': 'projectid-123',
            'use_existing_project': True
        }
        test_io.answers.append('projectid-123')
        args = self.project_id_prompt.prompt(test_io, '[1/2]', args)
        project_id = args['project_id']

        self.assertEqual(project_id, 'projectid-123')
        self.assertEqual(len(test_io.answers), 1)  # Answer is not used.

    @mock.patch('django_cloud_deploy.cloudlib.project.ProjectClient.'
                'project_exists',
                return_value=True)
    @mock.patch('django_cloud_deploy.cloudlib.project.ProjectClient.'
                'get_project_permissions',
                return_value=_FAKE_PERMISSIONS_RESPONSE_EDITOR)
    def test_existing_prompt_incorrect_permission_flag(self, *unused_mock):
        test_io = io.TestIO()
        args = {
            'backend': 'gae',
            'project_creation_mode': workflow.ProjectCreationMode.MUST_EXIST,
            'project_id': 'projectid-123',
            'use_existing_project': True
        }
        test_io.answers.append('projectid-123')

        # When passed as a flag, if the validation fails we expect the
        # command to exit out.
        with self.assertRaises(SystemExit):
            self.project_id_prompt.prompt(test_io, '[1/2]', args)

    @mock.patch('django_cloud_deploy.cloudlib.project.ProjectClient.'
                'project_exists',
                return_value=True)
    @mock.patch('django_cloud_deploy.cloudlib.project.ProjectClient.'
                'get_project_permissions',
                side_effect=[
                    _FAKE_PERMISSIONS_RESPONSE_EDITOR,
                    _FAKE_PERMISSIONS_RESPONSE_OWNER
                ])
    def test_existing_prompt_incorrect_permission_cli(self, *unused_mock):
        test_io = io.TestIO()
        args = {
            'backend': 'gae',
            'project_creation_mode': workflow.ProjectCreationMode.MUST_EXIST,
            'use_existing_project': True
        }
        test_io.answers.append('projectid-wrong')
        test_io.answers.append('projectid-123')
        args = self.project_id_prompt.prompt(test_io, '[1/2]', args)
        project_id = args['project_id']

        self.assertEqual(len(test_io.answers), 0)
        self.assertEqual(project_id, 'projectid-123')

    def test_prompt_default_project_name(self):
        test_io = io.TestIO()

        test_io.answers.append('')
        args = self.project_id_prompt.prompt(test_io, '[1/2]', {})
        project_id = args['project_id']
        self.assertRegex(project_id, r'django-\d{6}')
        self.assertEqual(len(test_io.answers), 0)  # All answers used.

    def test_prompt_bad_id(self):
        test_io = io.TestIO()

        test_io.answers.append('2short')
        test_io.answers.append('long-enough')
        args = self.project_id_prompt.prompt(test_io, '[1/2]', {})
        project_id = args['project_id']
        self.assertEqual(project_id, 'long-enough')
        self.assertEqual(len(test_io.answers), 0)  # All answers used.


class DjangoFilesystemPathTest(parameterized.TestCase):
    """Tests for prompt.DjangoFilesystemPath."""

    @classmethod
    def setUpClass(cls):
        cls.file_system_prompt = prompt.DjangoFilesystemPath()

    def test_prompt(self):
        test_io = io.TestIO()

        test_io.answers.append('/tmp/foo')
        args = self.file_system_prompt.prompt(test_io, '[1/2]', {})
        path = args['django_directory_path']
        self.assertEqual(path, '/tmp/foo')
        self.assertEqual(len(test_io.answers), 0)  # All answers used.

    @parameterized.parameters('y', 'Y')
    def test_prompt_existing_path(self, yes_replace_character):
        test_io = io.TestIO()

        with tempfile.NamedTemporaryFile() as f:
            test_io.answers.append(f.name)
            test_io.answers.append(yes_replace_character)
            args = self.file_system_prompt.prompt(test_io, '[1/2]', {})
            path = args['django_directory_path']
            self.assertEqual(path, f.name)
            self.assertEqual(len(test_io.answers), 0)  # All answers used.

    @parameterized.parameters('', 'n', 'N')
    def test_prompt_existing_path_new_path(self, no_replace_character):
        test_io = io.TestIO()

        with tempfile.NamedTemporaryFile() as f:
            test_io.answers.append(f.name)
            test_io.answers.append(no_replace_character)
            test_io.answers.append('/tmp/newname')
            args = self.file_system_prompt.prompt(test_io, '[1/2]', {})
            path = args['django_directory_path']
            self.assertEqual(path, '/tmp/newname')
            self.assertEqual(len(test_io.answers), 0)  # All answers used.

    @mock.patch('os.path.exists', return_value=False)
    def test_prompt_default(self, unused_mock):
        test_io = io.TestIO()

        test_io.answers.append('')
        self.file_system_prompt.prompt(test_io, '[1/2]', {})
        self.assertEqual(len(test_io.answers), 0)  # All answers used.

    def test_prompt_default_project_name(self):
        test_io = io.TestIO()

        test_io.answers.append('')
        args = {'project_name': 'Project Name'}
        args = self.file_system_prompt.prompt(test_io, '[1/2]', args)
        path = args['django_directory_path']
        self.assertIn('project-name', path)
        self.assertEqual(len(test_io.answers), 0)  # All answers used.


class PostgresPasswordPromptTest(parameterized.TestCase):
    """Tests for prompt.PostgresPasswordPrompt."""

    @classmethod
    def setUpClass(cls):
        cls.postgres_password_prompt = prompt.PostgresPasswordPrompt()

    def test_prompt(self):
        test_io = io.TestIO()

        test_io.password_answers.append('mypass32')
        test_io.password_answers.append('mypass32')
        args = self.postgres_password_prompt.prompt(test_io, '[1/2]', {})
        password = args['database_password']
        self.assertEqual(password, 'mypass32')
        self.assertEqual(len(test_io.password_answers), 0)  # All answers used.

    def test_bad_confirmation(self):
        test_io = io.TestIO()

        test_io.password_answers.append('mypass32')
        test_io.password_answers.append('mypass64')
        test_io.password_answers.append('secondtry2')
        test_io.password_answers.append('secondtry2')
        args = self.postgres_password_prompt.prompt(test_io, '[1/2]', {})
        password = args['database_password']
        self.assertEqual(password, 'secondtry2')
        self.assertEqual(len(test_io.password_answers), 0)  # All answers used.

    def test_bad_password(self):
        test_io = io.TestIO()

        test_io.password_answers.append(' ')
        test_io.password_answers.append('secondtry2')
        test_io.password_answers.append('secondtry2')
        args = self.postgres_password_prompt.prompt(test_io, '[1/2]', {})
        password = args['database_password']
        self.assertEqual(password, 'secondtry2')
        self.assertEqual(len(test_io.password_answers), 0)  # All answers used.


class DjangoSuperuserPasswordPromptTest(parameterized.TestCase):
    """Tests for prompt.DjangoSuperuserPasswordPrompt."""

    @classmethod
    def setUpClass(cls):
        cls.superuser_password_prompt = prompt.DjangoSuperuserPasswordPrompt()

    def test_prompt(self):
        test_io = io.TestIO()

        test_io.password_answers.append('mypass32')
        test_io.password_answers.append('mypass32')
        args = {'django_superuser_login': 'guido'}
        args = self.superuser_password_prompt.prompt(test_io, '[1/2]', args)
        password = args['django_superuser_password']
        self.assertEqual(password, 'mypass32')
        self.assertEqual(len(test_io.password_answers), 0)  # All answers used.

    def test_prompt_django_superuser_login(self):
        test_io = io.TestIO()

        test_io.password_answers.append('mypass32')
        test_io.password_answers.append('mypass32')
        args = {'django_superuser_login': 'guido'}
        args = self.superuser_password_prompt.prompt(test_io, '[1/2]', args)
        password = args['django_superuser_password']
        self.assertIn('guido', ' '.join(c for (c, *a) in test_io.tell_calls))
        self.assertEqual(password, 'mypass32')
        self.assertEqual(len(test_io.password_answers), 0)  # All answers used.

    def test_bad_confirmation(self):
        test_io = io.TestIO()

        test_io.password_answers.append('mypass32')
        test_io.password_answers.append('mypass64')
        test_io.password_answers.append('secondtry2')
        test_io.password_answers.append('secondtry2')
        args = self.superuser_password_prompt.prompt(test_io, '[1/2]', {})
        password = args['django_superuser_password']
        self.assertEqual(password, 'secondtry2')
        self.assertEqual(len(test_io.password_answers), 0)  # All answers used.

    def test_bad_password(self):
        test_io = io.TestIO()

        test_io.password_answers.append(' ')
        test_io.password_answers.append('secondtry2')
        test_io.password_answers.append('secondtry2')
        args = self.superuser_password_prompt.prompt(test_io, '[1/2]', {})
        password = args['django_superuser_password']
        self.assertEqual(password, 'secondtry2')
        self.assertEqual(len(test_io.password_answers), 0)  # All answers used.


_SINGLE_FAKE_ACCOUNT = [
    {
        'name': 'billingAccounts/1',
        'displayName': 'Fake Account 1',
        'open': True
    },
]

_FAKE_BILLING_ACCOUNTS = _SINGLE_FAKE_ACCOUNT + [
    {
        'name': 'billingAccounts/2',
        'displayName': 'Fake Account 2',
        'open': True
    },
]

_FAKE_BILLING_ACCOUNTS_AFTER_CREATE = _FAKE_BILLING_ACCOUNTS + [
    {
        'name': 'billingAccounts/3',
        'displayName': 'Fake Account 3',
        'open': True
    },
]

_FAKE_BILLING_INFO = {
    "name": "projects/project-abc/billingInfo",
    "projectId": "project-abc",
    "billingAccountName": "billingAccounts/0135D3-2564D9-F29D2E",
    "billingEnabled": True
}

_FAKE_NO_BILLING_INFO = {
    "name": "projects/project-abc/billingInfo",
    "projectId": "project-abc",
}


class BillingPromptTest(absltest.TestCase):
    """Tests for prompt.BillingPrompt."""

    @classmethod
    def setUpClass(cls):
        creds = mock.Mock(credentials.Credentials, authSpec=True)
        cls.billing_prompt = prompt.BillingPrompt(
            billing.BillingClient.from_credentials(creds))

    @mock.patch(('django_cloud_deploy.cloudlib.billing.BillingClient.'
                 'list_billing_accounts'),
                return_value=_FAKE_BILLING_ACCOUNTS)
    def test_prompt(self, unused_mock):
        test_io = io.TestIO()

        test_io.answers.append('1')
        args = self.billing_prompt.prompt(
            test_io,
            '[1/2]',
            {},
        )
        billing_name = args['billing_account_name']
        self.assertEqual(billing_name, _FAKE_BILLING_ACCOUNTS[0]['name'])
        self.assertEqual(len(test_io.answers), 0)  # All answers used.

    @mock.patch(('django_cloud_deploy.cloudlib.billing.BillingClient.'
                 'get_billing_account'),
                return_value=_FAKE_BILLING_INFO)
    def test_use_existing_project_with_billing(self, unused_mock):
        test_io = io.TestIO()
        args = {
            'project_creation_mode': workflow.ProjectCreationMode.MUST_EXIST,
            'project_id': 'project-abc'
        }

        args = self.billing_prompt.prompt(test_io, '[1/2]', args)
        billing_name = args['billing_account_name']
        self.assertEqual(billing_name, _FAKE_BILLING_INFO['billingAccountName'])
        self.assertEqual(len(test_io.answers), 0)  # All answers used.

    @mock.patch(('django_cloud_deploy.cloudlib.billing.BillingClient.'
                 'get_billing_account'),
                return_value=_FAKE_NO_BILLING_INFO)
    @mock.patch(('django_cloud_deploy.cloudlib.billing.BillingClient.'
                 'list_billing_accounts'),
                return_value=_FAKE_BILLING_ACCOUNTS)
    def test_use_existing_project_without_billing(self, *unused_mock):
        args = {
            'project_creation_mode': workflow.ProjectCreationMode.MUST_EXIST,
            'project_id': 'project-abc'
        }

        test_io = io.TestIO()

        test_io.answers.append('1')
        args = self.billing_prompt.prompt(test_io, '[1/2]', args)
        billing_name = args['billing_account_name']
        self.assertEqual(billing_name, _FAKE_BILLING_ACCOUNTS[0]['name'])
        self.assertEqual(len(test_io.answers), 0)  # All answers used.

    @mock.patch(('django_cloud_deploy.cloudlib.billing.BillingClient.'
                 'list_billing_accounts'),
                return_value=_FAKE_BILLING_ACCOUNTS)
    def test_numeric_choice_too_large(self, unused_mock):
        test_io = io.TestIO()

        test_io.answers.append('12345')
        test_io.answers.append('1')
        args = self.billing_prompt.prompt(test_io, '[1/2]', {})
        billing_name = args['billing_account_name']
        self.assertEqual(billing_name, _FAKE_BILLING_ACCOUNTS[0]['name'])
        self.assertEqual(len(test_io.answers), 0)  # All answers used.

    @mock.patch(('django_cloud_deploy.cloudlib.billing.BillingClient.'
                 'list_billing_accounts'),
                return_value=_FAKE_BILLING_ACCOUNTS)
    def test_numeric_choice_too_small(self, unused_mock):
        test_io = io.TestIO()

        test_io.answers.append('-12345')
        test_io.answers.append('1')
        args = self.billing_prompt.prompt(test_io, '[1/2]', {})
        billing_name = args['billing_account_name']
        self.assertEqual(billing_name, _FAKE_BILLING_ACCOUNTS[0]['name'])
        self.assertEqual(len(test_io.answers), 0)  # All answers used.

    @mock.patch(('django_cloud_deploy.cloudlib.billing.BillingClient.'
                 'list_billing_accounts'),
                return_value=_FAKE_BILLING_ACCOUNTS)
    def test_invalid_numeric_choice(self, unused_mock):
        test_io = io.TestIO()

        test_io.answers.append('a')
        test_io.answers.append('1')
        args = self.billing_prompt.prompt(test_io, '[1/2]', {})
        billing_name = args['billing_account_name']
        self.assertEqual(billing_name, _FAKE_BILLING_ACCOUNTS[0]['name'])
        self.assertEqual(len(test_io.answers), 0)  # All answers used.

    @mock.patch(('django_cloud_deploy.cloudlib.billing.BillingClient.'
                 'list_billing_accounts'),
                return_value=_SINGLE_FAKE_ACCOUNT)
    def test_invalid_numeric_choice_single_account(self, unused_mock):
        test_io = io.TestIO()

        test_io.answers.append('a')
        test_io.answers.append('1')
        args = self.billing_prompt.prompt(test_io, '[1/2]', {})
        billing_name = args['billing_account_name']
        self.assertEqual(billing_name, _SINGLE_FAKE_ACCOUNT[0]['name'])
        self.assertEqual(len(test_io.answers), 0)  # All answers used.
        error_msg = str(test_io.error_calls[0])
        self.assertIn('Please enter a numeric value', error_msg)

    @mock.patch(('django_cloud_deploy.cloudlib.billing.BillingClient.'
                 'list_billing_accounts'),
                return_value=_FAKE_BILLING_ACCOUNTS)
    def test_invalid_numeric_choice_multiple_accounts(self, unused_mock):
        test_io = io.TestIO()

        test_io.answers.append('a')
        test_io.answers.append('1')
        args = self.billing_prompt.prompt(test_io, '[1/2]', {})
        billing_name = args['billing_account_name']
        self.assertEqual(billing_name, _FAKE_BILLING_ACCOUNTS[0]['name'])
        self.assertEqual(len(test_io.answers), 0)  # All answers used.
        error_msg = str(test_io.error_calls[0])
        self.assertIn('Please enter a numeric value', error_msg)

    @mock.patch(('django_cloud_deploy.cloudlib.billing.BillingClient.'
                 'list_billing_accounts'),
                side_effect=[
                    _FAKE_BILLING_ACCOUNTS, _FAKE_BILLING_ACCOUNTS_AFTER_CREATE
                ])
    @mock.patch('webbrowser.open')
    def test_have_existing_accounts_create_new_account(self, *unused_mocks):
        test_io = io.TestIO()

        test_io.answers.append('')
        args = self.billing_prompt.prompt(test_io, '[1/2]', {})
        billing_name = args['billing_account_name']
        self.assertEqual(billing_name,
                         _FAKE_BILLING_ACCOUNTS_AFTER_CREATE[-1]['name'])
        self.assertEqual(len(test_io.answers), 0)  # All answers used.

    @mock.patch(('django_cloud_deploy.cloudlib.billing.BillingClient.'
                 'list_billing_accounts'),
                side_effect=[[], _SINGLE_FAKE_ACCOUNT])
    @mock.patch('webbrowser.open')
    def test_no_existing_accounts_create_new_account(self, *unused_mocks):
        test_io = io.TestIO()

        test_io.answers.append('')
        args = self.billing_prompt.prompt(test_io, '[1/2]', {})
        billing_name = args['billing_account_name']
        self.assertEqual(billing_name, _SINGLE_FAKE_ACCOUNT[0]['name'])
        self.assertEqual(len(test_io.answers), 0)  # All answers used.

    @mock.patch(('django_cloud_deploy.cloudlib.billing.BillingClient.'
                 'list_billing_accounts'),
                side_effect=[[], [], _SINGLE_FAKE_ACCOUNT])
    @mock.patch('webbrowser.open')
    def test_no_existing_accounts_create_new_account_success_second_time(
            self, *unused_mocks):
        test_io = io.TestIO()

        test_io.answers.append('')
        args = self.billing_prompt.prompt(test_io, '[1/2]', {})
        billing_name = args['billing_account_name']
        self.assertEqual(billing_name, _SINGLE_FAKE_ACCOUNT[0]['name'])
        self.assertEqual(len(test_io.answers), 0)  # All answers used.


class DjangoSettingsPathPromptTest(absltest.TestCase):
    """Tests for prompt.DjangoSettingsPathPrompt."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.django_settings_path_prompt = prompt.DjangoSettingsPathPrompt()

    def setUp(self):
        super().setUp()
        self.project_name = 'mysite'
        self.project_dir = tempfile.mkdtemp()
        management.call_command('startproject', self.project_name,
                                self.project_dir)

    def tearDown(self):
        super().tearDown()
        shutil.rmtree(self.project_dir)

    def test_prompt(self):
        test_io = io.TestIO()

        expected_settings_path = os.path.join(self.project_dir,
                                              self.project_name, 'settings.py')
        test_io.answers.append(expected_settings_path)
        before_sys_path = sys.path
        args = self.django_settings_path_prompt.prompt(
            test_io,
            '[2/2]',
            {'django_directory_path_cloudify': self.project_dir},
        )
        django_settings_path = args.get('django_settings_path', None)
        self.assertEqual(django_settings_path, expected_settings_path)
        self.assertEmpty(test_io.answers)  # All answers used.

        # Assert sys.path is not changed by the prompt
        self.assertCountEqual(before_sys_path, sys.path)

    def test_settings_file_not_found(self):
        test_io = io.TestIO()

        expected_settings_path = os.path.join(self.project_dir,
                                              self.project_name, 'settings.py')
        test_io.answers.append('<invalid_path>')
        test_io.answers.append(expected_settings_path)
        before_sys_path = sys.path
        args = self.django_settings_path_prompt.prompt(
            test_io,
            '[2/2]',
            {'django_directory_path_cloudify': self.project_dir},
        )
        django_settings_path = args.get('django_settings_path', None)
        self.assertEqual(django_settings_path, expected_settings_path)
        self.assertEmpty(test_io.answers)  # All answers used.

        # Assert sys.path is not changed by the prompt
        self.assertCountEqual(before_sys_path, sys.path)

    def test_settings_file_not_a_python_file(self):
        test_io = io.TestIO()

        invalid_settings_path = os.path.join(self.project_dir,
                                             self.project_name, 'settings')
        expected_settings_path = os.path.join(self.project_dir,
                                              self.project_name, 'settings.py')
        shutil.copyfile(expected_settings_path, invalid_settings_path)

        test_io.answers.append(invalid_settings_path)
        test_io.answers.append(expected_settings_path)
        before_sys_path = sys.path
        args = self.django_settings_path_prompt.prompt(
            test_io,
            '[2/2]',
            {'django_directory_path_cloudify': self.project_dir},
        )
        django_settings_path = args.get('django_settings_path', None)
        self.assertEqual(django_settings_path, expected_settings_path)
        self.assertEmpty(test_io.answers)  # All answers used.

        # Assert sys.path is not changed by the prompt
        self.assertCountEqual(before_sys_path, sys.path)

    def test_settings_file_invalid(self):
        test_io = io.TestIO()

        invalid_settings_path = os.path.join(self.project_dir,
                                             self.project_name,
                                             'settings_invalid.py')
        expected_settings_path = os.path.join(self.project_dir,
                                              self.project_name, 'settings.py')
        shutil.copyfile(expected_settings_path, invalid_settings_path)
        with open(invalid_settings_path) as f:
            file_content = f.read()
        with open(invalid_settings_path, 'wt') as f:
            file_content = file_content + '\nprint("12345"  # Invalid print'
            f.write(file_content)
        test_io.answers.append(invalid_settings_path)
        test_io.answers.append(expected_settings_path)
        before_sys_path = sys.path
        args = self.django_settings_path_prompt.prompt(
            test_io,
            '[2/2]',
            {'django_directory_path_cloudify': self.project_dir},
        )
        django_settings_path = args.get('django_settings_path', None)
        self.assertEqual(django_settings_path, expected_settings_path)
        self.assertEmpty(test_io.answers)  # All answers used.

        # Assert sys.path is not changed by the prompt
        self.assertCountEqual(before_sys_path, sys.path)


class DjangoRequirementsPathPromptTest(absltest.TestCase):
    """Tests for prompt.DjangoRequirementsPathPrompt."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.requirements_prompt = prompt.DjangoRequirementsPathPrompt()

    def setUp(self):
        super().setUp()
        self.project_name = 'mysite'
        self.project_dir = tempfile.mkdtemp()
        management.call_command('startproject', self.project_name,
                                self.project_dir)
        requirements_path = os.path.join(self.project_dir, 'requirements.txt')
        with open(requirements_path, 'wt') as f:
            f.write('six')

    def tearDown(self):
        super().tearDown()
        shutil.rmtree(self.project_dir)

    def test_prompt(self):
        test_io = io.TestIO()

        expected_requirements_path = os.path.join(self.project_dir,
                                                  'requirements.txt')
        test_io.answers.append(expected_requirements_path)
        args = self.requirements_prompt.prompt(
            test_io,
            '[2/2]',
            {'django_directory_path_cloudify': self.project_dir},
        )
        requirements_path = args.get('django_requirements_path', None)
        self.assertEqual(requirements_path, expected_requirements_path)
        self.assertEmpty(test_io.answers)  # All answers used.

    def test_default_value(self):
        test_io = io.TestIO()

        expected_requirements_path = os.path.join(self.project_dir,
                                                  'requirements.txt')
        test_io.answers.append('')
        args = self.requirements_prompt.prompt(
            test_io,
            '[2/2]',
            {'django_directory_path_cloudify': self.project_dir},
        )
        requirements_path = args.get('django_requirements_path', None)
        self.assertEqual(requirements_path, expected_requirements_path)
        self.assertEmpty(test_io.answers)  # All answers used.

    def test_requirements_file_not_found(self):
        test_io = io.TestIO()

        expected_requirements_path = os.path.join(self.project_dir,
                                                  'requirements.txt')
        test_io.answers.append('<invalid_path>')
        test_io.answers.append(expected_requirements_path)
        args = self.requirements_prompt.prompt(
            test_io,
            '[2/2]',
            {'django_directory_path_cloudify': self.project_dir},
        )
        requirements_path = args.get('django_requirements_path', None)
        self.assertEqual(requirements_path, expected_requirements_path)
        self.assertEmpty(test_io.answers)  # All answers used.


class DjangoProjectNamePromptCloudifyTest(absltest.TestCase):
    """Tests for prompt.DjangoProjectNamePromptCloudify."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.name_prompt = prompt.DjangoProjectNamePromptCloudify()

    def setUp(self):
        super().setUp()
        self.project_name = 'mysite'
        self.project_dir = tempfile.mkdtemp()
        management.call_command('startproject', self.project_name,
                                self.project_dir)

    def tearDown(self):
        super().tearDown()
        shutil.rmtree(self.project_dir)

    def test_prompt(self):
        test_io = io.TestIO()
        args = self.name_prompt.prompt(
            test_io,
            '[2/2]',
            {'django_directory_path_cloudify': self.project_dir},
        )
        project_name = args.get('django_project_name_cloudify', None)
        self.assertEqual(self.project_name, project_name)
        self.assertEmpty(test_io.answers)  # All answers used.

    def test_cannot_find_project_name(self):
        test_io = io.TestIO()
        manage_py_path = os.path.join(self.project_dir, 'manage.py')
        with open(manage_py_path) as f:
            file_content = f.read()
        with open(manage_py_path, 'wt') as f:
            file_content = file_content.replace(
                '\'{}.settings\''.format(self.project_name), 'module_variable')
            f.write(file_content)
        test_io.answers.append('mysite')
        args = self.name_prompt.prompt(
            test_io,
            '[2/2]',
            {'django_directory_path_cloudify': self.project_dir},
        )
        project_name = args.get('django_project_name_cloudify', None)
        self.assertEqual(self.project_name, project_name)
        self.assertEmpty(test_io.answers)  # All answers used.


if __name__ == '__main__':
    absltest.main()
