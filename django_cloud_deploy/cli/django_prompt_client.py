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

import os
from typing import List

from django_cloud_deploy.utils import workflow_io


class DjangoConfig(object):

    def __init__(self, django_name: str, project_dir: str, apps: List[str]):
        self.django_name = django_name
        self.project_dir = project_dir
        self.apps = apps


class DjangoPromptClient(object):
    """A class to ask users to provide Django project information."""

    def __init__(self, io: workflow_io.IO):
        self.workflow = workflow_io.Workflow(io)

    def prompt_user_for_info(self):
        django_config = {
            'django_name': self._prompt_django_name(),
            'project_dir': self._prompt_project_dir(),
            'apps': self._prompt_app_names()
        }
        return DjangoConfig(**django_config)

    @staticmethod
    def _is_alnum(input_str):
        return input_str.isalnum()

    @staticmethod
    def _is_valid_appname(input_str):
        apps = input_str.split(',')
        for app in apps:
            if not app.isalnum():
                return False
        return True

    def _prompt_project_dir(self):
        home_dir = os.path.expanduser('~')
        default_value = os.path.join(home_dir, 'djangogke_project')
        project_dir_prompt = (
            'Provide the absolute Project Directoy Path, '
            'use [{}] by pressing enter:').format(default_value)

        return self.workflow.ask(project_dir_prompt, default_value)

    def _prompt_django_name(self):
        """Ask user to give the name of their Django project."""
        default_value = 'mysite'
        django_project_name_prompt = (
            'Provide the Django Project Name, '
            'use [{}] by pressing enter:').format(default_value)

        error_msg = ('Django Project Name should only include letters and '
                     'numbers. Please use another name and try again.')
        return self.workflow.ask(django_project_name_prompt, default_value,
                                 self._is_alnum, error_msg)

    def _prompt_app_names(self):
        """Ask user to give a list of the names of their Django apps.

    The app names should be separated by commas.

    Returns:
      List[str], list of app names.
    """
        default_value = 'polls'
        app_name_prompt = ('Provide App Names separated by commas, '
                           'use [{}] by pressing enter:').format(default_value)
        error_msg = ('Django App Name should only include letters and '
                     'numbers, or the input you provided are not separated by '
                     'commas. Please use other names and try again.')

        apps = self.workflow.ask(app_name_prompt, default_value,
                                 self._is_valid_appname, error_msg)
        return apps.split(',')
