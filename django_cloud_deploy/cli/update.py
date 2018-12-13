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
import sys

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

    parser.add_argument(
        '--backend',
        dest='backend',
        type=str,
        default='gke',
        choices=['gae', 'gke'],
        help='The desired backend to update the Django App on.')


def main(args: argparse.Namespace, console: io.IO = io.ConsoleIO()):

    try:
        tool_requirements.check_and_handle_requirements(console, args.backend)
    except tool_requirements.MissingRequirementsError as e:
        console.tell('Please install the following requirements:')
        for req in e.missing_requirements:
            console.tell('* {}: {}'.format(req.name,
                                           req.how_to_install_message))
        return

    prompt_order = [
        'credentials',
        'database_password',
        'django_directory_path',
    ]

    required_parameters_to_prompt = {
        'credentials': prompt.CredentialsPrompt,
        'database_password': prompt.PostgresPasswordUpdatePrompt,
        'django_directory_path': prompt.DjangoFilesystemPathUpdate,
    }

    # Parameters that were *not* provided as command flags.
    remaining_parameters_to_prompt = {}

    actual_parameters = {}

    for parameter_name, prompter in required_parameters_to_prompt.items():
        value = getattr(args, parameter_name, None)
        if value is not None:
            try:
                prompter.validate(value)
            except ValueError as e:
                print(e, file=sys.stderr)
                sys.exit(1)
            actual_parameters[parameter_name] = value
        else:
            remaining_parameters_to_prompt[parameter_name] = prompter

    if remaining_parameters_to_prompt:

        num_steps = len(remaining_parameters_to_prompt)
        console.tell('<b>{} steps to update project</b>'.format(num_steps))
        console.tell()
        parameter_and_prompt = sorted(
            remaining_parameters_to_prompt.items(),
            key=lambda i: prompt_order.index(i[0]))

        for step, (parameter_name, prompter) in enumerate(parameter_and_prompt):
            step = '<b>[{}/{}]</b>'.format(step + 1, num_steps)
            actual_parameters[parameter_name] = prompter.prompt(
                console, step, actual_parameters)

    workflow_manager = workflow.WorkflowManager(
        actual_parameters['credentials'], args.backend)
    workflow_manager.update_project(actual_parameters['django_directory_path'],
                                    actual_parameters['database_password'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='')
    args = parser.parse_args()
    main(args)
