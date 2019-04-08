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
"""Unit test for django_cloud_deploy/skeleton/requirements_parser.py."""

import os
import shutil
import tempfile
import unittest

from django_cloud_deploy.skeleton import requirements_parser


class RequirementsParserTest(unittest.TestCase):
    """Unit test for django_cloud_deploy/skeleton/requirements_parser.py."""

    def setUp(self):
        super().setUp()
        self._project_dir = tempfile.mkdtemp()

    def tearDown(self):
        super().tearDown()
        shutil.rmtree(self._project_dir)

    def test_parse_single_line(self):
        requirements = [
            'six', 'urllib3', 'django', 'backoff', 'mysqlclient', 'gunicorn',
            'wheel', 'google-cloud-logging'
        ]
        lines = [
            'six==1.2', 'urllib3>=4.5.6', 'Django<=7.8', 'backoff',
            'mysqlclient~=1.3.4', 'gunicorn[1,7.8, 2.3.4]', 'wheel   == 1.2.3',
            'google-cloud-logging; sys_platform == \'win32\''
        ]
        for i in range(len(lines)):
            self.assertEqual(requirements_parser.parse_line(lines[i]),
                             requirements[i])

    def test_parse_requirements(self):
        requirements = ['six', 'urllib3', 'django', 'backoff']
        lines = ['six==1.2', 'urllib3>=4.5.6', 'Django<=7.8', 'backoff']
        requirements_file_path = os.path.join(self._project_dir,
                                              'requirements.txt')
        with open(requirements_file_path, 'wt') as f:
            f.write('\n'.join(lines))
        results = requirements_parser.parse(requirements_file_path)
        for requirement in requirements:
            self.assertIn(requirement, results)

    def test_parse_requirements_with_comments(self):
        requirements = ['six', 'urllib3', 'django', 'backoff']
        lines = [
            'six==1.2', '# Comment', 'urllib3>=4.5.6', 'Django<=7.8', 'backoff'
        ]
        requirements_file_path = os.path.join(self._project_dir,
                                              'requirements.txt')
        with open(requirements_file_path, 'wt') as f:
            f.write('\n'.join(lines))
        results = requirements_parser.parse(requirements_file_path)
        for requirement in requirements:
            self.assertIn(requirement, results)
        self.assertEqual(len(requirements), len(results))

    def test_parse_requirements_with_empty_lines(self):
        requirements = ['six', 'urllib3', 'django', 'backoff']
        lines = ['six==1.2', '    ', 'urllib3>=4.5.6', 'Django<=7.8', 'backoff']
        requirements_file_path = os.path.join(self._project_dir,
                                              'requirements.txt')
        with open(requirements_file_path, 'wt') as f:
            f.write('\n'.join(lines))
        results = requirements_parser.parse(requirements_file_path)
        for requirement in requirements:
            self.assertIn(requirement, results)
        self.assertEqual(len(requirements), len(results))

    def test_parse_requirements_recursively(self):
        requirements = ['six', 'urllib3', 'django', 'backoff']
        lines1 = ['six==1.2', 'urllib3>=4.5.6']
        lines2 = ['-r requirements1.txt', 'Django<=7.8', 'backoff']
        requirements_file_path1 = os.path.join(self._project_dir,
                                               'requirements1.txt')
        with open(requirements_file_path1, 'wt') as f:
            f.write('\n'.join(lines1))
        requirements_file_path2 = os.path.join(self._project_dir,
                                               'requirements2.txt')
        with open(requirements_file_path2, 'wt') as f:
            f.write('\n'.join(lines2))
        results = requirements_parser.parse(requirements_file_path2)
        for requirement in requirements:
            self.assertIn(requirement, results)
        self.assertEqual(len(requirements), len(results))
