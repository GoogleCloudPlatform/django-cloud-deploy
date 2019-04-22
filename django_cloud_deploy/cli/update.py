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

from django_cloud_deploy import config
from django_cloud_deploy import tool_requirements
from django_cloud_deploy.cli import io
from django_cloud_deploy.cli import prompt
import django_cloud_deploy.workflow as workflow


class InvalidConfigError(Exception):
    """A error occurred when fail to read required information from config."""


def add_arguments(parser):

    parser.add_argument(
        '--project-path',
        dest='django_directory_path_update',
        help='The location where the generated Django project code should be '
        'stored.')

    parser.add_argument('--database-password',
                        dest='database_password',
                        help='The password for the default database user.')

    parser.add_argument('--credentials',
                        dest='credentials',
                        help=('The credentials object to use for deployment. '
                              'Test only, do not use.'))

    parser.add_argument(
        '--credentials-path',
        dest='credentials_path',
        help=('The absolute path of the credentials file to use for '
              'deployment.'))

    parser.add_argument(
        '--cluster-name',
        dest='cluster_name',
        nargs='+',
        help=('Name of the cluster to use for deploying on GKE. Test only, do '
              'not use.'))

    parser.add_argument(
        '--database-instance-name',
        dest='database_instance_name',
        nargs='+',
        help=('Name of the Cloud SQL instance used for deployment. Test only, '
              'do not use.'))


def main(args: argparse.Namespace, console: io.IO = io.ConsoleIO()):

    actual_parameters = {
        'cluster_name': getattr(args, 'cluster_name', None),
        'database_instance_name': getattr(args, 'database_instance_name', None),
    }
    prompt_args = {**vars(args), **actual_parameters}
    root_prompt = prompt.RootPrompt()
    actual_parameters = root_prompt.prompt(prompt.Command.UPDATE, console,
                                           prompt_args)

    # This got moved from the start because we wanted to save the user from
    # giving us another bit of information that we can automatically retrieve
    # It will be rare if they are updating, that they do not have the
    # requirements.
    django_dir = actual_parameters['django_directory_path_update']
    config_obj = config.Configuration(django_dir)
    backend = config_obj.get('backend')
    if not backend:
        raise InvalidConfigError(
            'Configuration file in [{}] does not contain enough '
            'information to update a Django project.'.format(django_dir))

    if not tool_requirements.check_and_handle_requirements(console, backend):
        return

    workflow_manager = workflow.WorkflowManager(
        actual_parameters['credentials'])
    workflow_manager.update_project(
        django_directory_path=actual_parameters['django_directory_path_update'],
        database_password=actual_parameters['database_password'],
        cluster_name=actual_parameters['cluster_name'],
        database_instance_name=actual_parameters['database_instance_name'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='')
    args = parser.parse_args()
    main(args)
