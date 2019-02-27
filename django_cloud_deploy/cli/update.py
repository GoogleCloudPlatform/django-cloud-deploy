# Copyright 2018 Google LLC
#
# Licensed under the Apache License, Versconsolen 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITconsoleNS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissconsolens and
# limitatconsolens under the License.
"""Create and deploy a new Django project on GKE."""

import argparse

from django_cloud_deploy import tool_requirements
from django_cloud_deploy.cli import io
from django_cloud_deploy.cli import prompt
import django_cloud_deploy.workflow as workflow


def add_arguments(parser):

    parser.add_argument(
        '--project-path',
        dest='django_directory_path',
        help='The location where the generated Django project code should be '
        'stored.')

    parser.add_argument(
        '--database-password',
        dest='database_password',
        help='The password for the default database user.')

    parser.add_argument(
        '--credentials',
        dest='credentials',
        help=('The file path of the credentials file to use for update. '
              'Test only, do not use.'))


def main(args: argparse.Namespace, console: io.IO = io.ConsoleIO()):

    if not tool_requirements.check_and_handle_requirements(
            console, args.backend):
        return

    root_prompt = prompt.RootPrompt()
    actual_parameters = root_prompt.prompt(prompt.Command.UPDATE, console,
                                           vars(args))

    workflow_manager = workflow.WorkflowManager(
        actual_parameters['credentials'])
    workflow_manager.update_project(
        actual_parameters['django_directory_path_update'],
        actual_parameters['database_password'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='')
    args = parser.parse_args()
    main(args)
