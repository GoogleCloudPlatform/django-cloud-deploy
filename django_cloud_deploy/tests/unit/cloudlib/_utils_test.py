# Copyright 2019 Google LLC
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
"""Tests for the cloudlib._utils module."""

from absl.testing import absltest

from django_cloud_deploy.cloudlib import _utils


class AuthorizedHttpFake(object):
    """Fakes the google_auth_httplib2.AuthorizedHttp Class"""

    def request(self, uri, method='GET', body=None, headers=None, **kwargs):
        """Mock Implementation of httplib2's Http.request."""
        user_agent = None
        if headers:
            user_agent = headers.get('user-agent')
        return None, user_agent


class UtilsTestCase(absltest.TestCase):
    """Test case for Utils functions."""

    def setUp(self):
        self.mockHttp = AuthorizedHttpFake()

    def test_set_user_agent(self):
        user_agent = 'django-cloud-deploy/1.0'
        self.assertIsNone(self.mockHttp.request(None)[1])
        self.mockHttp = _utils.set_user_agent(self.mockHttp, user_agent)
        self.assertEquals(user_agent, self.mockHttp.request(None)[1])
