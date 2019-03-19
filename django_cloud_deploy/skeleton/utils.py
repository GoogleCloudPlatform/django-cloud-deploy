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
from typing import Optional


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

    # TODO: This does not handle line continuation. Fix it.
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


def is_valid_django_project(django_directory_path: str) -> bool:
    """Returns whether the given path contains a valid Django project.

    Args:
        django_directory_path: Absolute path of django project directory.

    Returns:
        Whether the given path contains a valid Django project.
    """

    # TODO: handle more complex cases.
    manage_py_path = os.path.join(django_directory_path, 'manage.py')
    return os.path.exists(manage_py_path)


def guess_settings_path(django_directory_path: str) -> Optional[str]:
    """Guess the absolute path of settings file of the django project.

    The logic is as the follows:
        1. Find the local settings file path from manage.py.
        2. Find settings files containing "prod" in the same directory with
           local settings file. If this file is found, return it. If not, return
           local settings file.
        3. If manage.py does not exist or cannot find local settings file path
           from manage.py, return an empty string.
    Args:
        django_directory_path: Absolute path of a Django project.

    Returns:
        Absolute path of settings.py of the given Django project. If it cannot
        be found, return None.
    """

    manage_py_path = os.path.join(django_directory_path, 'manage.py')
    if not os.path.exists(manage_py_path):
        return None

    with open(manage_py_path) as f:
        file_content = f.read()

        # In manage.py, there is a line as the follows:
        # "os.environ.setdefault('DJANGO_SETTINGS_MODULE',
        #                        '{{ project_name }}.settings')"
        # It is possible that this statement is write in multiple lines
        settings_module_line = re.search(
            r'os\.environ\.setdefault\([^\)]+,[^\)]+\)', file_content)
        if not settings_module_line:
            return None

        # The matching result will be like
        # "os.environ.setdefault('DJANGO_SETTINGS_MODULE', \n'mysite.settings')"
        # Find strings between "" or ''
        raw_settings_module = re.findall(
            r'[\"\'][\w+\.]+[\"\']', settings_module_line.group(0))
        # Remove empty spaces and delete quotation marks at the start and end
        settings_module = raw_settings_module[-1].strip()[1:-1]

    relative_settings_path = settings_module.replace('.', '/') + '.py'
    absolute_settings_path = os.path.join(
        django_directory_path, relative_settings_path)
    if not os.path.exists(absolute_settings_path):
        return None
    settings_dir = os.path.dirname(absolute_settings_path)
    files_list = os.listdir(settings_dir)
    for file in files_list:
        if 'prod' in file:
            return os.path.join(settings_dir, file)
    return absolute_settings_path
