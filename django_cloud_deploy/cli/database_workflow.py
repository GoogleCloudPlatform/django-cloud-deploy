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

import contextlib
import os
import re
import signal
import subprocess

import pexpect

from django_cloud_deploy.cloudlib import database
from django_cloud_deploy.utils import base_client
from django_cloud_deploy.utils import workflow_io


class CloudSqlProxyError(Exception):
    pass


class DatabaseWorkflow(base_client.BaseClient):
    """

  Download any necesarry requirements
  Create a Cloud SQL PostgreSQL instance.
  Retrieve ConnectionName value
  Start the Cloud SQL Proxy
  Create Cloud SQL User and DB

  """

    def __init__(self,
                 io: workflow_io.IO,
                 project_id: str,
                 project_name: str,
                 project_dir: str,
                 database_client: database.DatabaseClient,
                 cloud_sql_proxy_path: str = 'cloud_sql_proxy',
                 zone: str = 'us-west1',
                 debug=False):
        super().__init__(debug)
        self.workflow = workflow_io.Workflow(io)
        self.project_id = project_id
        self.project_name = project_name
        self.project_dir = project_dir
        self.cloud_sql_proxy_path = cloud_sql_proxy_path
        self.database_client = database_client
        self.zone = zone

    def create_database_workflow(self):
        """Create a cloud database and set password for default user.

    Follows the steps found @
    https://cloud.google.com/python/django/kubernetes-engine

    regarding setting up a database.
    """
        self.workflow.tell('Creating Cloud SQL instance. This should take '
                           'around 5 minutes.')

        instance_name = self.project_name + '-instance'
        db_name = self.project_name + '-db'

        os.environ.setdefault('DATABASE_USER', 'postgres')
        os.environ.setdefault('DATABASE_PASSWORD', self._password)

        self.database_client.create_instance_sync(self.project_id,
                                                  instance_name)
        self.database_client.create_database_sync(self.project_id,
                                                  instance_name, db_name)
        self.database_client.set_database_password(
            self.project_id, instance_name, 'postgres', self._password)

    def create_superuser_workflow(self):
        """Create a super user in cloud sql database.

    This function should be called after we did the following:
      1. Generated the Django project source files.
      2. Created the cloud sql instance and database user.
    """

        # Create a superuser without password.
        # Actually django allow us to set the password of users with
        # 'createsuperuser' command. However, because we are running
        # django-admin in a subprocess instead of a shell, we are not
        # able to provide input to that command. So we have to firstly
        # create a superuser and set password afterwards.
        # See https://github.com/django/django/blob/master/django/contrib/auth/management/commands/createsuperuser.py#L80  # noqa: E501
        print(
            'Creating a superuser for your Django admin site.\n'
            'This superuser account is useful to manage content on your site.')

        with self._with_cloud_sql_proxy():
            password = os.environ['DATABASE_PASSWORD']
            settings_module = '.'.join([self.project_name, 'remote_settings'])
            createsuperuser_args = [
                'django-admin', 'createsuperuser', '='.join([
                    '--username', self._superuser_name
                ]), '='.join(['--email', self._superuser_email]),
                '='.join(['--pythonpath', self.project_dir]), '='.join(
                    ['--settings', settings_module]), '--noinput'
            ]
            subprocess.check_call(createsuperuser_args)

            # Set superuser password
            changepassword_args = ((
                'django-admin changepassword {} --pythonpath={} '
                '--settings={}')).format(self._superuser_name, self.project_dir,
                                         settings_module)

            # 'changepassword' command spawns the following output:
            # Password: <type your password>
            # Password (again): <type your password>
            # If your password is too common, it will ask you to use another
            # password and repeat the process above.
            # TODO: Handle too common passwords.
            proc = pexpect.spawn(changepassword_args)
            proc.expect(b'Password: ')
            proc.sendline(password)
            proc.expect(r'Password \(again\):')
            proc.sendline(password)
            proc.interact()

    def migrate_database_workflow(self):
        """Migrate to cloud sql database."""

        with self._with_cloud_sql_proxy():
            settings_module = '.'.join([self.project_name, 'remote_settings'])

            # "makemigrations" will generate migration files based on
            # definitions in models.py.
            makemigrations_args = [
                'django-admin', 'makemigrations',
                '='.join(['--pythonpath', self.project_dir]), '='.join(
                    ['--settings', settings_module])
            ]
            subprocess.check_call(makemigrations_args)

            # "migrate" will modify cloud sql database.
            migrate_args = [
                'django-admin', 'migrate',
                '='.join(['--pythonpath', self.project_dir]), '='.join(
                    ['--settings', settings_module])
            ]
            subprocess.check_call(migrate_args)

    def _get_instance_connection_string(self):
        return '{0}:{1}:{2}-instance'.format(self.project_id, self.zone,
                                             self.project_name)

    @contextlib.contextmanager
    def _with_cloud_sql_proxy(self):
        try:
            instance_connection_string = self._get_instance_connection_string()
            instance_flag = '-instances={}=tcp:5432'.format(
                instance_connection_string)
            process = pexpect.spawn(
                self.cloud_sql_proxy_path, args=[instance_flag])
            CLOUD_SQL_READY = 'Ready for new connections'
            process.expect(
                CLOUD_SQL_READY, timeout=5)  # To avoid race condition
            yield

        except pexpect.exceptions.TIMEOUT:
            raise CloudSqlProxyError(
                'Cloud SQL Proxy was unable to start correctly')
        finally:
            process.kill(signal.SIGTERM)

    @staticmethod
    def _is_valid_superuser_name(username):
        return username.isalnum()

    def ask_for_superuser_name(self):
        default_name = 'admin'
        error_msg = ('Superuser Name should only include letters and '
                     'numbers. Please use another name and try again.')
        self._superuser_name = self.workflow.ask(
            ('Provide superuser name for your Django admin site. This account '
             'is useful to manage content on your site. Use [{}] '
             'by pressing enter:').format(default_name), default_name,
            self._is_valid_superuser_name, error_msg)
        return self._superuser_name

    @staticmethod
    def _is_valid_email(email):
        return bool(re.match(r'[^@]+@[^@]+\.[^@]+', email))

    def ask_for_superuser_email(self):
        default_email = 'test@gmail.com'
        error_msg = (
            'Invalid email address. The format of email address should '
            'be "example@example.com". Please use another address and '
            'try again.')
        self._superuser_email = self.workflow.ask(
            ('Provide superuser email for your Django admin site. Use [{}] '
             'by pressing enter:').format(default_email), default_email,
            self._is_valid_email, error_msg)
        return self._superuser_email

    def ask_for_password(self):
        self.workflow.tell(
            'Provide password for postgres database. We will use '
            'this to reset password of the default user '
            '"postgres".')
        self._password = self.workflow.ask_password()
        return self._password
