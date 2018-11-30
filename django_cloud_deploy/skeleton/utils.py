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
"""Utility functions related to Django project source files."""

import os
import re


class ProjectContentError(Exception):
    """An error thrown when Django project name cannot be determined."""


def get_django_project_name(django_directory_path: str):
    """Returns Django project name given a Django project directory.

    In manage.py, there is a line as the follows:
    "os.environ.setdefault('DJANGO_SETTINGS_MODULE',
                           '{{ project_name }}.settings')"

    We can determine the project name from this line.

    Args:
        django_directory_path: Absolute path of django project directory.

    Raises:
        ProjectContentError: When the function cannot find Django project name.
    """
    manage_py_path = os.path.join(django_directory_path, 'manage.py')
    if not os.path.exists(manage_py_path):
        raise ProjectContentError(
            ('manage.py does not exist under Django project directory. The '
             'project name cannot be determined.'))
    with open(manage_py_path) as f:
        lines = f.readlines()
        target = ''
        for line in lines:
            if 'DJANGO_SETTINGS_MODULE' in line:
                target = line
                break
        # Find strings between "" or ''
        strings = re.findall(r'[\"\'][\w+\.]+[\"\']', target)
        for string in strings:

            # Delete quotation marks at the start and end
            string = string[1:-1]
            if '.' in string:
                return string[:string.find('.')]
    raise ProjectContentError('Django project name cannot be determined.')
