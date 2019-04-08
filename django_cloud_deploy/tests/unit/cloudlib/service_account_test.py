# Copyright 2018 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Tests for the cloudlib.service_account module."""

import base64
from unittest import mock

from absl.testing import absltest
from googleapiclient import errors

from django_cloud_deploy.cloudlib import service_account
from django_cloud_deploy.tests.unit.cloudlib.lib import http_fake

PROJECT_ID = 'fake_project_id'
SERVICE = 'fake_service'

FAKE_SERVICE_ACCOUNT = 'serviceAccount:{}@{}.gserviceaccount.com'.format(
    SERVICE, PROJECT_ID)

FAKE_ROLE = 'roles/fake'

FAKE_IAM_POLICY = {
    'bindings': [
        {
            'members': [FAKE_SERVICE_ACCOUNT],
            'role': FAKE_ROLE
        },
    ],
}

INVALID_IAM_POLICY = {'invalid_key': 'invalid_value'}

PRIVATE_KEY_DECRYPTED = b"""{
    "type": "service_account",
    "private_key": "123456"
}"""

FAKE_CREATE_KEY_RESPONSE = {
    'privateKeyData': base64.standard_b64encode(PRIVATE_KEY_DECRYPTED)
}


class ServiceAccoutKeysFake(object):

    def __init__(self):
        self.key_count = 0

    def create(self, name, body):
        if 'invalid' in name:
            return http_fake.HttpRequestFake(
                errors.HttpError(http_fake.HttpResponseFake(400),
                                 b'invalid resource name'))
        else:
            self.key_count += 1
            return http_fake.HttpRequestFake(FAKE_CREATE_KEY_RESPONSE)


class ServiceAccountsFake(object):

    def __init__(self):
        self.service_account_keys_fake = ServiceAccoutKeysFake()
        self.service_accounts = [SERVICE]

    def create(self, name, body):
        if 'invalid' in body['accountId']:
            return http_fake.HttpRequestFake(
                errors.HttpError(http_fake.HttpResponseFake(400),
                                 b'invalid account id'))
        elif body['accountId'] in self.service_accounts:
            return http_fake.HttpRequestFake(
                errors.HttpError(http_fake.HttpResponseFake(409),
                                 b'service account already exists'))
        else:
            self.service_accounts.append(body['accountId'])
            return http_fake.HttpRequestFake({'name': name})

    def keys(self):
        return self.service_account_keys_fake


class ProjectsFake(object):
    """A fake object returned by ...projects()."""

    def __init__(self):
        self.service_accounts_fake = ServiceAccountsFake()
        self.iam_policy = FAKE_IAM_POLICY

    def getIamPolicy(self, resource):
        if 'invalid' in resource:
            return http_fake.HttpRequestFake(INVALID_IAM_POLICY)
        else:
            return http_fake.HttpRequestFake(self.iam_policy)

    def setIamPolicy(self, resource, body):
        if 'bindings' in body['policy']:
            self.iam_policy = body['policy']
        return http_fake.HttpRequestFake(body['policy'])

    def serviceAccounts(self):
        return self.service_accounts_fake


class CloudResourceManagerFake(object):

    def __init__(self):
        self.projects_fake = ProjectsFake()

    def projects(self):
        return self.projects_fake


class IamServiceFake(object):

    def __init__(self):
        self.projects_fake = ProjectsFake()

    def projects(self):
        return self.projects_fake


class ServiceAccountClientTestCase(absltest.TestCase):
    """Test case for service_account.ServiceAccountClient."""

    def setUp(self):
        self._iam_service_fake = IamServiceFake()
        self._cloudresourcemanager_fake = CloudResourceManagerFake()
        self._service_account_client = service_account.ServiceAccountClient(
            self._iam_service_fake, self._cloudresourcemanager_fake)

    def test_update_iam_policy_role_already_exist(self):
        """Test adding a new member to an existing role."""
        policy = FAKE_IAM_POLICY
        service_account_id = 'fake-service-account'
        project_id = PROJECT_ID
        role = FAKE_ROLE
        member = ('serviceAccount:{}@{}.iam.gserviceaccount.com'.format(
            service_account_id, project_id))
        new_policy = self._service_account_client._generate_updated_iam_policy(
            policy, member, role)
        self.assertIn(member, new_policy['bindings'][0]['members'])

    def test_update_iam_policy_member_already_exist(self):
        """Test adding an existing member to an existing role.

        This should not change the iam policy.
        """
        policy = FAKE_IAM_POLICY
        role = FAKE_ROLE
        member = FAKE_SERVICE_ACCOUNT
        new_policy = self._service_account_client._generate_updated_iam_policy(
            policy, member, role)
        self.assertDictEqual(FAKE_IAM_POLICY, new_policy)

    def test_update_iam_policy_role_not_exist(self):
        policy = FAKE_IAM_POLICY
        role = 'role/new_fake_role'
        member = FAKE_SERVICE_ACCOUNT
        new_policy = self._service_account_client._generate_updated_iam_policy(
            policy, member, role)
        self.assertEqual(len(new_policy['bindings']), 2)
        self.assertEqual(role, new_policy['bindings'][1]['role'])
        self.assertIn(member, new_policy['bindings'][1]['members'])

    def test_create_service_account_success(self):
        service_account_id = 'test_create_service_account_success'
        service_account_name = 'Test Create Service Account Success'
        self._service_account_client.create_service_account(
            PROJECT_ID, service_account_id, service_account_name, [FAKE_ROLE])

        # Assert the service account is created
        all_service_accounts = (self._iam_service_fake.projects_fake.
                                service_accounts_fake.service_accounts)
        self.assertIn(service_account_id, all_service_accounts)

        # Assert roles are granted
        member = ('serviceAccount:{}@{}.iam.gserviceaccount.com'.format(
            service_account_id, PROJECT_ID))
        policy = self._cloudresourcemanager_fake.projects_fake.iam_policy
        self.assertIn(member, policy['bindings'][0]['members'])

    def test_create_service_account_invalid_arguments(self):
        service_account_id = 'invalid'
        service_account_name = 'Invalid'

        with self.assertRaises(service_account.ServiceAccountCreationError):
            self._service_account_client.create_service_account(
                PROJECT_ID, service_account_id, service_account_name,
                [FAKE_ROLE])

        # Assert the service account is not created
        all_service_accounts = (self._iam_service_fake.projects_fake.
                                service_accounts_fake.service_accounts)
        self.assertNotIn(service_account_id, all_service_accounts)

        # Assert iam policy is unchanged
        policy = self._cloudresourcemanager_fake.projects_fake.iam_policy
        self.assertDictEqual(FAKE_IAM_POLICY, policy)

    def test_create_service_account_duplicate(self):
        service_account_id = SERVICE
        service_account_name = 'Fake Service Account'

        self._service_account_client.create_service_account(
            PROJECT_ID, service_account_id, service_account_name, [FAKE_ROLE])

        # Assert the service account list is unchanged
        all_service_accounts = (self._iam_service_fake.projects_fake.
                                service_accounts_fake.service_accounts)
        self.assertCountEqual([SERVICE], all_service_accounts)

        # Assert iam policy is unchanged
        policy = self._cloudresourcemanager_fake.projects_fake.iam_policy
        self.assertDictEqual(FAKE_IAM_POLICY, policy)

    def test_create_service_account_server_returns_invalid_policy(self):
        service_account_id = (
            'test_create_service_account_returns_invalid_policy')
        service_account_name = 'Test Service Account'

        project_id = 'invalid'

        with self.assertRaises(service_account.ServiceAccountCreationError):
            self._service_account_client.create_service_account(
                project_id, service_account_id, service_account_name,
                [FAKE_ROLE])

        # Assert the service account list is unchanged
        all_service_accounts = (self._iam_service_fake.projects_fake.
                                service_accounts_fake.service_accounts)
        self.assertCountEqual([SERVICE], all_service_accounts)

        # Assert iam policy is unchanged
        policy = self._cloudresourcemanager_fake.projects_fake.iam_policy
        self.assertDictEqual(FAKE_IAM_POLICY, policy)

    def test_create_service_account_set_iam_policy_fail(self):
        service_account_id = 'test_create_service_account_set_iam_policy_fail'
        service_account_name = 'Test Service Account'

        project_id = 'invalid'

        with mock.patch(('django_cloud_deploy.cloudlib.service_account.'
                         'ServiceAccountClient._get_iam_policy'),
                        autoSpec=True) as mock_get_iam_policy:
            mock_get_iam_policy.return_value = INVALID_IAM_POLICY
            with self.assertRaises(service_account.ServiceAccountCreationError):
                self._service_account_client.create_service_account(
                    project_id, service_account_id, service_account_name, [])

            # Assert the service account is created
            all_service_accounts = (self._iam_service_fake.projects_fake.
                                    service_accounts_fake.service_accounts)
            self.assertIn(service_account_id, all_service_accounts)

            # Assert iam policy is unchanged
            policy = self._cloudresourcemanager_fake.projects_fake.iam_policy
            self.assertDictEqual(FAKE_IAM_POLICY, policy)

    def test_create_service_account_key_success(self):
        service_account_id = 'test_create_service_account_key_success'

        key = self._service_account_client.create_key(PROJECT_ID,
                                                      service_account_id)

        self.assertEqual(key, PRIVATE_KEY_DECRYPTED.decode('utf-8'))

        key_count = (self._iam_service_fake.projects_fake.service_accounts_fake.
                     service_account_keys_fake.key_count)
        self.assertEqual(key_count, 1)

    def test_create_service_account_key_failure(self):
        service_account_id = 'test_create_service_account_key_failure'
        project_id = 'invalid'

        with self.assertRaises(service_account.ServiceAccountKeyCreationError):
            self._service_account_client.create_key(project_id,
                                                    service_account_id)

        key_count = (self._iam_service_fake.projects_fake.service_accounts_fake.
                     service_account_keys_fake.key_count)
        self.assertEqual(key_count, 0)

    def test_request_with_retry_simple_success(self):
        responses = ['valid_value']
        request = http_fake.HttpRequestFakeMultiple(responses)
        with mock.patch(__name__ + '.ProjectsFake.setIamPolicy',
                        return_value=request):
            response = (
                self._service_account_client._update_iam_policy_with_retry(
                    PROJECT_ID, FAKE_SERVICE_ACCOUNT, [FAKE_ROLE]))
            self.assertEqual(request.call_count, 1)
            self.assertEqual(response, 'valid_value')

    def test_request_with_retry_success_at_second_time(self):
        responses = [
            errors.HttpError(http_fake.HttpResponseFake(409),
                             b'service account already exists'), 'valid_value'
        ]
        request = http_fake.HttpRequestFakeMultiple(responses)
        with mock.patch(__name__ + '.ProjectsFake.setIamPolicy',
                        return_value=request):
            response = (
                self._service_account_client._update_iam_policy_with_retry(
                    PROJECT_ID, FAKE_SERVICE_ACCOUNT, [FAKE_ROLE]))
            self.assertEqual(request.call_count, 2)
            self.assertEqual(response, 'valid_value')

    def test_request_with_retry_fail(self):
        err = errors.HttpError(http_fake.HttpResponseFake(409),
                               b'service account already exists')
        responses = [err] * 5
        request = http_fake.HttpRequestFakeMultiple(responses)
        with mock.patch(__name__ + '.ProjectsFake.setIamPolicy',
                        return_value=request):
            with self.assertRaises(errors.HttpError):
                self._service_account_client._update_iam_policy_with_retry(
                    PROJECT_ID, FAKE_SERVICE_ACCOUNT, [FAKE_ROLE])

    def test_request_with_retry_other_error_code(self):
        err1 = errors.HttpError(http_fake.HttpResponseFake(409),
                                b'service account already exists')
        err2 = errors.HttpError(http_fake.HttpResponseFake(400),
                                b'invalid request')
        responses = [err1, err2, err1]
        request = http_fake.HttpRequestFakeMultiple(responses)
        with mock.patch(__name__ + '.ProjectsFake.setIamPolicy',
                        return_value=request):
            with self.assertRaises(errors.HttpError) as cm:
                self._service_account_client._update_iam_policy_with_retry(
                    PROJECT_ID, FAKE_SERVICE_ACCOUNT, [FAKE_ROLE])

            exception = cm.exception
            self.assertEqual(exception.resp.status, 400)
