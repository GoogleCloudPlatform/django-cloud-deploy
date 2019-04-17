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
"""Create and deploy a new Django project on GKE."""

import argparse

from django_cloud_deploy import tool_requirements
from django_cloud_deploy import workflow
from django_cloud_deploy.cli import io
from django_cloud_deploy.cli import prompt
from django_cloud_deploy.utils import survey


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
        '--billing-account-name',
        dest='billing_account_name',
        help='Name of the GCP Billing account name to be associated with the '
        'project.')

    parser.add_argument('--database-password',
                        dest='database_password',
                        help='The password for the default database user.')

    parser.add_argument('--django-project-name',
                        dest='django_project_name',
                        help='The name of the Django project e.g. "mysite".')

    parser.add_argument('--django-app-name',
                        dest='django_app_name',
                        help='The name of the Django app e.g. "poll".')

    parser.add_argument(
        '--django-superuser-login',
        dest='django_superuser_login',
        help='The login name of the Django superuser e.g. "admin".')

    parser.add_argument('--django-superuser-password',
                        dest='django_superuser_password',
                        help='The password of the Django superuser.')

    parser.add_argument('--django-superuser-email',
                        dest='django_superuser_email',
                        help='The e-mail address of the Django superuser.')

    parser.add_argument(
        '--use-existing-project',
        dest='use_existing_project',
        action='store_true',
        help='Flag to indicate using a new or existing project.')

    parser.add_argument('--backend',
                        dest='backend',
                        type=str,
                        default='gae',
                        choices=['gae', 'gke'],
                        help='The desired backend to deploy the Django App on.')

    parser.add_argument('--credentials',
                        dest='credentials',
                        help=('The credentials object to use for deployment. '
                              'Test only, do not use.'))

    parser.add_argument(
        '--credentials-path',
        dest='credentials_path',
        help=('The absolute path of the credentials file to use for '
              'deployment.'))

    parser.add_argument('--bucket-name',
                        dest='bucket_name',
                        help=('Name of the GCS bucket to serve static content. '
                              'Test only, do not use.'))

    parser.add_argument(
        '--service-accounts',
        dest='service_accounts',
        nargs='+',
        help=('Service account objects to create for deployment. '
              'Test only, do not use.'))

    parser.add_argument('--services',
                        dest='services',
                        nargs='+',
                        help=('Services necessary for the deployment. '
                              'Test only, do not use.'))

    parser.add_argument(
        '--appengine-service-name',
        dest='appengine_service_name',
        nargs='+',
        help=('App engine service name. Test only, do not use.'))


def main(args: argparse.Namespace, console: io.IO = io.ConsoleIO()):
    if not tool_requirements.check_and_handle_requirements(
            console, args.backend):
        return

    actual_parameters = {
        'project_creation_mode': workflow.ProjectCreationMode.CREATE,
        'bucket_name': getattr(args, 'bucket_name', None),
        'service_accounts': getattr(args, 'service_accounts', None),
        'services': getattr(args, 'services', None),
        'appengine_service_name': getattr(args, 'appengine_service_name', None)
    }

    prompt_args = {**vars(args), **actual_parameters}
    root_prompt = prompt.RootPrompt()
    actual_parameters = root_prompt.prompt(prompt.Command.NEW, console,
                                           prompt_args)
    workflow_manager = workflow.WorkflowManager(
        actual_parameters['credentials'])

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
            appengine_service_name=actual_parameters['appengine_service_name'],
            cloud_storage_bucket_name=actual_parameters['bucket_name'],
            backend=args.backend)
    except workflow.ProjectExistsError:
        console.error('A project with id "{}" already exists'.format(
            actual_parameters['project_id']))

    survey.prompt_for_survey(console)
    return admin_url


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='')
    add_arguments(parser)
    arguments = parser.parse_args()
    main(arguments)
