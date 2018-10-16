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

import argparse
import configparser
import os
import sys
import warnings

from django_cloud_deploy.cli import billing_workflow
from django_cloud_deploy.cli import database_workflow
from django_cloud_deploy.cli import django_prompt_client
from django_cloud_deploy.cli import google_client
from django_cloud_deploy.cli import requirements_client
from django_cloud_deploy.cli import service_account_client
from django_cloud_deploy.cloudlib import auth
from django_cloud_deploy.cloudlib import database
from django_cloud_deploy.cloudlib import enable_service
from django_cloud_deploy.cloudlib import project
from django_cloud_deploy.deploygke import deploygke
from django_cloud_deploy.skeleton import source_generator
from django_cloud_deploy.utils import workflow_io
from django_cloud_deploy.workflow import _auth
from django_cloud_deploy.workflow import _enable_service

CONFIG_DIR = os.path.join(os.path.expanduser('~'),
                          '.config',
                          'django_cloud_deploy')
CONFIG_PATH = os.path.join(CONFIG_DIR, 'default_config')
TOTAL_STEPS = 9


class MissingDependencyError(Exception):
    pass


def generate_section_header(step, section_name):
    return '\n\n**Step {} of {}: {}**\n\n'.format(step, TOTAL_STEPS,
                                                  section_name)


def _handle_authentication(debug=False):
    print('\n\n**Authentication**\n\n')
    auth_client = auth.AuthClient(debug)
    auth_workflow = _auth.AuthWorkflow(auth_client)
    return auth_workflow.get_credentials()


def _handle_requirements(r_client: requirements_client.RequirementsClient):
    missing_requirements = r_client.missing_requirements()
    if missing_requirements:
        print('Please install: \n')
        for req in missing_requirements:
            print('* {}'.format(req))
        print('\nExiting the program. Please install all requirements\n')
        sys.exit()
    if not r_client.is_docker_usable():
        print('\nExiting the program. Please follow instructions for docker.\n')
        sys.exit()
    print('All requirements met.')


def _handle_cloud_proxy_requirement(
        r_client: requirements_client.RequirementsClient) -> str:
    try:
        return r_client.get_cloud_sql_proxy()
    except requirements_client.MissingDependencyError:
        print('\nExiting the program. Please install all requirements\n')
        sys.exit()
    except NotImplementedError as e:
        print('\nExiting the program. {}\n'.format(e.message))
        sys.exit()


def _enable_apis(credentials, project_id):
    print('This should take < 2 minutes.\n' 'Enabling the following API\'s:\n')
    enable_service_client = enable_service.EnableServiceClient.from_credentials(
        credentials)
    enable_service_workflow = _enable_service.EnableServiceWorkflow(
        enable_service_client)
    services_to_enable = enable_service_workflow.load_services()
    for service in services_to_enable:
        print('* {}'.format(service['title']))
    enable_service_workflow.enable_required_services(
        project_id=project_id, services=services_to_enable)


def _save_config(project_id, project_name, project_dir):
    """Generate a config file and save it to ~/.config/default_config."""
    config = configparser.ConfigParser()
    config['DEFAULT'] = {
        'project_id': project_id,
        'project_name': project_name,
        'project_dir': project_dir
    }
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_PATH, 'w') as config_file:
        config.write(config_file)


def _read_config():
    config = configparser.ConfigParser()
    config.read(CONFIG_PATH)
    return config['DEFAULT']


def update(debug=False):
    """Update the Django project on GKE."""
    config = _read_config()
    project_id = config['project_id']
    project_name = config['project_name']
    project_dir = config['project_dir']

    console = workflow_io.Console()
    requirements = requirements_client.RequirementsClient.load_requirements()
    r_client = requirements_client.RequirementsClient(requirements, console)
    cloud_sql_proxy = _handle_cloud_proxy_requirement(r_client)

    db_workflow = database_workflow.DatabaseWorkflow(
        console,
        project_id,
        project_name,
        project_dir,
        cloud_sql_proxy_path=cloud_sql_proxy,
        database_client=None,
        debug=debug)
    os.environ.setdefault('DATABASE_USER', 'postgres')
    password = console.ask('Please enter your database password:', hide=True)
    os.environ.setdefault('DATABASE_PASSWORD', password)

    db_workflow.migrate_database_workflow()
    deploygke_client = deploygke.DeploygkeWorkflow(
        project_id, project_name, project_dir, debug=debug)
    deploygke_client.updategke()


def new(debug=False):
    """Create a new Django GKE project."""

    # TODO: Add a layer of abstraction
    console = workflow_io.Console()

    # Make sure user has requirements for all the commands
    print(generate_section_header(1, 'Requirements'))
    requirements = requirements_client.RequirementsClient.load_requirements()
    r_client = requirements_client.RequirementsClient(requirements, console)
    _handle_requirements(r_client)
    cloud_sql_proxy = _handle_cloud_proxy_requirement(r_client)

    # Make the user login
    print(generate_section_header(2, 'Authentication'))
    credentials = _handle_authentication(debug)

    project_client = project.ProjectClient.from_credentials(credentials)

    # Create project in GCP and set it in Gcloud as current project
    print(generate_section_header(3, 'Create GCP Project'))
    goog_client = google_client.GoogleClient(
        console, project_client, debug=debug)
    project_id = goog_client.create_project_workflow()

    # Confirm Billing has been set on the project
    print(generate_section_header(4, 'Billing Set Up'))
    bill_client = billing_workflow.BillingWorkflow(project_id, console)
    bill_client.billing_workflow()

    # Prompt Django Info
    print(generate_section_header(5, 'Django Set Up'))
    django_prompter = django_prompt_client.DjangoPromptClient(console)
    django_config = django_prompter.prompt_user_for_info()

    # Create Django Files
    generator = source_generator.DjangoSourceFileGenerator()
    generator.generate_all_source_files(project_id, django_config.django_name,
                                        django_config.apps,
                                        django_config.project_dir)

    # Create DB instance and configurations

    database_client = database.DatabaseClient.from_credentials(credentials)
    db_workflow = database_workflow.DatabaseWorkflow(
        workflow_io.Console(),
        project_id,
        django_config.django_name,
        django_config.project_dir,
        cloud_sql_proxy_path=cloud_sql_proxy,
        database_client=database_client,
        debug=debug)

    db_workflow.ask_for_password()
    superuser_name = db_workflow.ask_for_superuser_name()
    db_workflow.ask_for_superuser_email()

    # Create DB instance and configurations
    print(generate_section_header(6, 'Database Set Up'))
    db_workflow.create_database_workflow()

    # Enable Api's required used by this tool
    print(generate_section_header(7, 'Enable API\'s'))
    _enable_apis(credentials, project_id)

    sa_client = service_account_client.ServiceAccountClient(
        project_id, django_config.django_name, debug=debug)
    service_account_key_path = sa_client.create_service_account_workflow()

    # Migrations
    print(generate_section_header(8, 'Django Migrations'))
    db_workflow.migrate_database_workflow()
    db_workflow.create_superuser_workflow()

    # Deployment
    print(generate_section_header(9, 'Deployment'))
    deploygke_client = deploygke.DeploygkeWorkflow(
        project_id,
        django_config.django_name,
        django_config.project_dir,
        debug=debug)
    deploygke_client.deploygke(service_account_key_path, superuser_name)
    _save_config(project_id, django_config.django_name,
                 django_config.project_dir)


def main():
    warnings.filterwarnings(
        'ignore',
        ('Your application has authenticated using end user credentials from '
         'Google Cloud SDK.'))

    parser = argparse.ArgumentParser(description='')
    parser.add_argument(
        '--debug',
        action='store_true',
        help='display extended debugging information')
    subparsers = parser.add_subparsers(title='subcommands')
    new_parser = subparsers.add_parser(
        'new',
        description=('Create a new Django project and deploy it to Google '
                     'Kubernetes Engine.'))
    new_parser.set_defaults(func=new)
    update_parser = subparsers.add_parser(
        'update',
        description=('Deploys an Django project, previously created with '
                     'django_cloud_deploy, on Google Kubernetes Engine.'))
    update_parser.set_defaults(func=update)
    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)
    args = parser.parse_args()

    args.func(args.debug)


if __name__ == '__main__':
    main()
