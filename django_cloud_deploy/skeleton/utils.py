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


def parse_settings_module(file_path: str) -> Optional[str]:
    """Parse the Django settings module from the given file.

    The function expects there is code like the following in the given file:
        "os.environ.setdefault('DJANGO_SETTINGS_MODULE',
                               '{{ settings_module }}')"
    {{ settings_module }} is like "mysite.settings.dev"

    Args:
        file_path: Absolute path of the file to parse.

    Returns:
        The settings module. For example, "mysite.settings.dev". If the given
            file does not exist or the content of it does not contain the
            settings module, return None.
    """
    if not os.path.exists(file_path):
        return None

    with open(file_path) as f:
        file_content = f.read()

        settings_module_line = re.search(
            r'os\.environ\.setdefault\([^\)]+,[^\)]+\)', file_content)
        if not settings_module_line:
            return None

        # The matching result will be like
        # "os.environ.setdefault('DJANGO_SETTINGS_MODULE', \n'mysite.settings')"
        # Find strings between "" or ''
        raw_settings_module = re.findall(r'[\"\'][\w+\.]+[\"\']',
                                         settings_module_line.group(0))

        # raw_settings_module should be like
        # ['"DJANGO_SETTINGS_MODULE"', '"mysite.settings"']
        # If it is not like this, then we are not able to parse the settings
        # module.
        if len(raw_settings_module) < 2:
            return None

        commas = ['\'', '\"']
        for module in raw_settings_module:
            # The settings module is not between " or '
            if (len(module) < 2 or module[0] not in commas or
                    module[-1] not in commas):
                return None
        # Remove empty spaces and delete quotation marks at the start and end
        settings_module = raw_settings_module[-1].strip()[1:-1]
        return settings_module


def get_local_settings_module(django_directory_path: str) -> Optional[str]:
    """Returns the local settings module of a Django project.

    In manage.py, there is a line as the follows:
        "os.environ.setdefault('DJANGO_SETTINGS_MODULE',
                               '{{ local_settings_module }}')"
    {{ local_settings_module }} is like "mysite.settings.dev"

    Args:
        django_directory_path: Absolute path of django project directory.

    Returns:
        The settings module used for local development. For example,
            "mysite.settings.dev". If manage.py does not exist or the content
            of it does not contain the local settings module, return None.
    """
    manage_py_path = os.path.join(django_directory_path, 'manage.py')
    return parse_settings_module(manage_py_path)


def get_django_project_name(django_directory_path: str) -> Optional[str]:
    """Returns Django project name given a Django project directory.

    In manage.py, there is a line as the follows:
    "os.environ.setdefault('DJANGO_SETTINGS_MODULE',
                           '{{ project_name }}.settings')"

    We can determine the project name from this line.

    Args:
        django_directory_path: Absolute path of django project directory.
    """

    settings_module = get_local_settings_module(django_directory_path)
    if not settings_module:
        return None
    return settings_module.split('.')[0]


def is_valid_django_project(django_directory_path: str) -> bool:
    """Returns whether the given path contains a valid Django project.

    Args:
        django_directory_path: Absolute path of django project directory.

    Returns:
        Whether the given path contains a valid Django project.
    """

    # TODO: handle more complex cases.
    manage_py_path = os.path.join(django_directory_path, 'manage.py')
    if not os.path.exists(manage_py_path):
        return False
    with open(manage_py_path) as f:
        file_content = f.read()
        settings_module_line = re.search(
            r'os\.environ\.setdefault\([^\)]+,[^\)]+\)', file_content)
        if not settings_module_line:
            return False
    return True


def guess_requirements_path(django_directory_path: str,
                            project_name: str) -> Optional[str]:
    """Guess the absolute path of requirements.txt.

    The logic is as the follows:
        1. If "requirements.txt" exists in the given directory, return it.
        2. If "requirements.txt" exists in django_directory/<project_name>,
           return it.
        3. If files like "prod.txt", "deploy.txt" exists in
           django_directory/requirements, return it.
        4. If none of the above exists, return None.

    Args:
        django_directory_path: Absolute path of a Django project.
        project_name: Name of the Django project. e.g. mysite.

    Returns:
        Absolute path of requirements.txt of the given Django project. If it
        cannot be found, return None.
    """

    if os.path.exists(django_directory_path):
        files_list = os.listdir(django_directory_path)
        if 'requirements.txt' in files_list:
            return os.path.join(django_directory_path, 'requirements.txt')

    project_dir = os.path.join(django_directory_path, project_name)
    if os.path.exists(project_dir):
        files_list = os.listdir(project_dir)
        if 'requirements.txt' in files_list:
            return os.path.join(project_dir, 'requirements.txt')

    requirements_dir = os.path.join(django_directory_path, 'requirements')
    if os.path.exists(requirements_dir):
        files_list = os.listdir(requirements_dir)
        for file_name in files_list:
            if 'prod' in file_name or 'deploy' in file_name:
                return os.path.join(requirements_dir, file_name)
    return None


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

    settings_module = get_local_settings_module(django_directory_path)
    if not settings_module:
        return None
    relative_settings_path = settings_module.replace('.', '/') + '.py'
    absolute_settings_path = os.path.join(django_directory_path,
                                          relative_settings_path)
    if not os.path.exists(absolute_settings_path):
        return None

    settings_dir = os.path.dirname(absolute_settings_path)
    files_list = os.listdir(settings_dir)
    for file in files_list:
        if 'prod' in file:
            return os.path.join(settings_dir, file)
    return absolute_settings_path
