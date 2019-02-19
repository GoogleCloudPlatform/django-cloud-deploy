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
"""Unit test for django_cloud_deploy/crash_handling."""

import unittest
from unittest import mock
from urllib import parse

from django_cloud_deploy import crash_handling
from django_cloud_deploy.cli import io


@mock.patch('tempfile.mkstemp', return_value=(1, '/tmp/tmpfile'))
@mock.patch('os.fdopen')
class CrashHandlingTest(unittest.TestCase):
    """Unit test for django_cloud_deploy.crash_handling."""

    _COLLECTED_INFO = ('Django Cloud Deploy:', 'Gcloud Version',
                       'Docker Version', 'Cloud SQL Proxy Version',
                       'Python Version', 'Traceback', 'Platform',
                       'Issue running command')

    def assert_valid_issue_title(self, title, err):
        self.assertIn(type(err).__name__, title)
        self.assertIn(str(err), title)

    def assert_valid_issue_body(self, body):
        for keyword in self._COLLECTED_INFO:
            self.assertIn(keyword, body)

    def parse_body_and_title_from_url(self, url):
        params = parse.parse_qs(parse.urlparse(url).query)
        return params['title'][0], params['body'][0], params['labels'][0]

    @mock.patch('webbrowser.open')
    def test_create_issue(self, mock_open_browser, *unused_mocks):
        test_io = io.TestIO()
        test_io.answers.append('Y')  # Agree to open browser to create an issue
        error = KeyError('Test KeyError')
        crash_handling.handle_crash(error, 'command_fake', test_io)
        self.assertEqual(mock_open_browser.call_count, 1)
        url = mock_open_browser.call_args[0][0]
        title, body, label = self.parse_body_and_title_from_url(url)
        self.assert_valid_issue_title(title, error)
        self.assert_valid_issue_body(body)
        self.assertEqual(label, crash_handling._ISSUE_LABEL)
        self.assertIn(type(error).__name__, title)

    @mock.patch('webbrowser.open')
    def test_not_creating_issue(self, mock_open_browser, *unused_mocks):
        test_io = io.TestIO()
        test_io.answers.append('N')  # Not creating Github issues
        error = KeyError('Test KeyError')
        crash_handling.handle_crash(error, 'command_fake', test_io)
        mock_open_browser.assert_not_called()

    @mock.patch('webbrowser.open')
    def test_ignore_user_error(self, mock_open_browser, *unused_mocks):
        test_io = io.TestIO()
        test_io.answers.append('Y')  # Agree to open browser to create an issue
        error = KeyError('Test KeyError')
        with self.assertRaises(KeyError):
            try:
                raise crash_handling.UserError() from error
            except Exception as e:
                crash_handling.handle_crash(e, 'command_fake', test_io)
        mock_open_browser.assert_not_called()
