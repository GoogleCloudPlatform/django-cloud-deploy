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
from django_cloud_deploy import workflow
from django_cloud_deploy.cli import io
from django_cloud_deploy.cli import prompt


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

    parser.add_argument(
        '--backend',
        dest='backend',
        type=str,
        default='gke',
        choices=['gae', 'gke'],
        help='The desired backend to deploy the Django App on.')

    parser.add_argument(
        '--credentials',
        dest='credentials',
        help=('The file path of the credentials file to use for deployment. '
              'Test only, do not use.'))

    parser.add_argument(
        '--bucket-name',
        dest='bucket_name',
        help=('Name of the GCS bucket to serve static content. '
              'Test only, do not use.'))

    parser.add_argument(
        '--service-accounts',
        dest='service_accounts',
        nargs='+',
        help=('Service account objects to create for deployment. '
              'Test only, do not use.'))

    parser.add_argument(
        '--services',
        dest='services',
        nargs='+',
        help=('Services necessary for the deployment. '
              'Test only, do not use.'))


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
        'project_creation_mode': workflow.ProjectCreationMode.CREATE,
        'bucket_name': getattr(args, 'bucket_name', None),
        'service_accounts': getattr(args, 'service_accounts', None),
        'services': getattr(args, 'services', None)
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

    if args.use_existing_project:
        actual_parameters['project_creation_mode'] = (
            workflow.ProjectCreationMode.MUST_EXIST)
        remaining_parameters_to_prompt['project_name'] = (
            prompt.GoogleCloudProjectNamePrompt)
        remaining_parameters_to_prompt['project_id'] = (
            prompt.ExistingProjectIdPrompt)

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
        actual_parameters['credentials'], args.backend)

    try:
        admin_url = workflow_manager.create_and_deploy_new_project(
            project_name=actual_parameters['project_name'],
            project_id=actual_parameters['project_id'],
            project_creation_mode=actual_parameters['project_creation_mode'],
            billing_account_name=actual_parameters['billing_account_name'],
            django_project_name=actual_parameters['django_project_name'],
            django_app_name=actual_parameters['django_app_name'],
            django_superuser_name=actual_parameters['django_superuser_login'],
            django_superuser_email=actual_parameters['django_superuser_email'],
            django_superuser_password=actual_parameters[
                'django_superuser_password'],
            django_directory_path=actual_parameters['django_directory_path'],
            database_password=actual_parameters['database_password'],
            required_services=actual_parameters['services'],
            required_service_accounts=actual_parameters['service_accounts'],
            cloud_storage_bucket_name=actual_parameters['bucket_name'],
            backend=args.backend)
        return admin_url
    except workflow.ProjectExistsError:
        console.error('A project with id "{}" already exists'.format(
            actual_parameters['project_id']))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='')
    add_arguments(parser)
    args = parser.parse_args()
    main(args)
