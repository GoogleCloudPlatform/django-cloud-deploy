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
        '--project-name',
        dest='project_name',
        help='The name of the Google Cloud Platform project. Can be changed.')

    parser.add_argument(
        '--project-id',
        dest='project_id',
        help='The unique id to use when creating the Google Cloud Platform '
        'project. Can not be changed.')

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
        '--django-project-name',
        dest='django_project_name',
        help='The name of the Django project e.g. "mysite".')

    parser.add_argument(
        '--django-app-name',
        dest='django_app_name',
        help='The name of the Django app e.g. "poll".')

    parser.add_argument(
        '--django-superuser-login',
        dest='django_superuser_login',
        help='The login name of the Django superuser e.g. "admin".')

    parser.add_argument(
        '--django-superuser-password',
        dest='django_superuser_password',
        help='The password of the Django superuser.')

    parser.add_argument(
        '--django-superuser-email',
        dest='django_superuser_email',
        help='The e-mail address of the Django superuser.')

    parser.add_argument(
        '--use-existing-project',
        dest='use_existing_project',
        action='store_true',
        help='Flag to indicate using a new or existing project.')


def main(args: argparse.Namespace):

    console = io.ConsoleIO()
    tool_requirements.check_and_handle_requirements(console)

    prompt_order = [
        'credentials',
        'project_id',
        'project_name',
        'billing_account_name',
        'database_password',
        'django_directory_path',
        'django_project_name',
        'django_app_name',
        'django_superuser_login',
        'django_superuser_password',
        'django_superuser_email',
    ]

    required_parameters_to_prompt = {
        'credentials': prompt.CredentialsPrompt,
        'project_id': prompt.ProjectIdPrompt,
        'project_name': prompt.GoogleCloudProjectNamePrompt,
        'billing_account_name': prompt.BillingPrompt,
        'database_password': prompt.PostgresPasswordPrompt,
        'django_directory_path': prompt.DjangoFilesystemPath,
        'django_project_name': prompt.DjangoProjectNamePrompt,
        'django_app_name': prompt.DjangoAppNamePrompt,
        'django_superuser_login': prompt.DjangoSuperuserLoginPrompt,
        'django_superuser_password': prompt.DjangoSuperuserPasswordPrompt,
        'django_superuser_email': prompt.DjangoSuperuserEmailPrompt
    }

    # Parameters that were *not* provided as command flags.
    remaining_parameters_to_prompt = {}

    actual_parameters = {
        # TODO: Some arguments will need to be prepopulated here.
    }

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

    use_existing_project = getattr(args, 'use_existing_project', False)

    if use_existing_project:
        actual_parameters['use_existing_project'] = use_existing_project
        remaining_parameters_to_prompt['project_name'] = (
            prompt.GoogleCloudProjectNamePrompt)

    if remaining_parameters_to_prompt:

        num_steps = len(remaining_parameters_to_prompt)
        console.tell(
            '<b>{} steps to setup your new project</b>'.format(num_steps))
        console.tell()
        parameter_and_prompt = sorted(
            remaining_parameters_to_prompt.items(),
            key=lambda i: prompt_order.index(i[0]))

        for step, (parameter_name, prompter) in enumerate(parameter_and_prompt):
            step = '<b>[{}/{}]</b>'.format(step + 1, num_steps)
            actual_parameters[parameter_name] = prompter.prompt(
                console, step, actual_parameters,
                actual_parameters.get('credentials', None))

    workflow_manager = workflow.WorkflowManager(
        actual_parameters['credentials'])
    workflow_manager.create_and_deploy_new_project(
        actual_parameters['project_name'],
        actual_parameters['project_id'],
        actual_parameters['billing_account_name'],
        actual_parameters['django_project_name'],
        actual_parameters['django_app_name'],
        actual_parameters['django_superuser_login'],
        actual_parameters['django_superuser_email'],
        actual_parameters['django_superuser_password'],
        actual_parameters['django_directory_path'],
        actual_parameters['database_password'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='')
    add_arguments(parser)
    args = parser.parse_args()
    main(args)
