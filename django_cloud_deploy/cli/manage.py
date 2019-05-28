# Copyright 2019 Google LLC
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
"""Run Django management commands related to databases.

These management commands should have effect on Cloud SQL database, instead of
local database.
"""

import argparse
import os
import subprocess
from typing import List

from django_cloud_deploy import config
from django_cloud_deploy.cli import io
from django_cloud_deploy.cloudlib import auth
from django_cloud_deploy.cloudlib import database
import portpicker

_SUPPORTED_COMMANDS = frozenset([
    'dbshell',
    'dumpdata',
    'flush',
    'inspectdb',
    'loaddata',
    'makemigrations',
    'migrate',
    'showmigrations',
    'sqlflush',
    'sqlmigrate',
    'sqlsequencereset',
    'squashmigrations',
    'changepassword',
    'createsuperuser',
])


def _execute(args: List[str], console: io.IO):
    """Wraps the execution of a management command with Cloud SQL Proxy.

    Args:
        args: The full arguments of a Django management command. For example,
            ['migrate'], ['showmigrations']
        console: Handles the input/output with the user.
    """
    current_dir = os.path.abspath(os.path.expanduser('.'))

    if not config.Configuration.exist(current_dir):
        console.error(('The Django project in "{}" is not deployed yet. Please '
                       'deploy it to be able to use the management '
                       'commands').format(current_dir))
        return

    # Assume the project was previously deployed with Django Cloud Deply,
    # then we should be able to get the following parameters
    config_obj = config.Configuration(current_dir)
    django_settings_path = config_obj.get('django_settings_path')
    root, _ = os.path.splitext(django_settings_path)
    settings_module = '.'.join(root.split('/')[:-1] + ['cloud_settings'])
    instance_name = config_obj.get('database_instance_name')
    project_id = config_obj.get('project_id')

    creds = auth.AuthClient.get_default_credentials()
    if not creds:
        creds = auth.AuthClient.create_default_credentials()
    database_client = database.DatabaseClient.from_credentials(creds)
    cloud_sql_proxy_port = portpicker.pick_unused_port()
    os.environ['CLOUD_SQL_PROXY_PORT'] = str(cloud_sql_proxy_port)
    with database_client.with_cloud_sql_proxy(project_id=project_id,
                                              instance_name=instance_name,
                                              port=cloud_sql_proxy_port):
        arguments = [
            'django-admin', *args, '='.join(['--pythonpath', current_dir]),
            '='.join(['--settings', settings_module])
        ]
        try:
            subprocess.check_call(arguments)
        except subprocess.CalledProcessError:
            # Only show error messages from Django, ignore traceback from DCD
            pass


def main(args: argparse.Namespace, console: io.IO = io.ConsoleIO()):

    vargs = vars(args)
    if not vargs.get('command_rest'):
        console.error('Please enter the management command.')
        return

    command_rest = vargs.get('command_rest')
    management_command = command_rest[0]
    if management_command not in _SUPPORTED_COMMANDS:
        console.error(('Command "{}" is not supported by Django Cloud '
                       'Deploy.').format(management_command))

    _execute(command_rest, console)
