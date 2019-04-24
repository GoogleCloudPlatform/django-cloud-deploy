# Copyright 2018 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Manages Google Cloud SQL instances, databases and users.

See https://cloud.google.com/sql/docs/
"""

import contextlib
import os
import signal
import shutil
import subprocess
import time
from typing import Optional

from django import db
from django.core import management
from django_cloud_deploy import crash_handling

import pexpect
from pexpect import popen_spawn

from googleapiclient import discovery
from googleapiclient import errors
from google.auth import credentials


class DatabaseError(Exception):
    pass


class DatabaseClient(object):
    """A class for managing Google Cloud SQL objects."""

    def __init__(self, sqladmin_service: discovery.Resource):
        self._sqladmin_service = sqladmin_service

    @classmethod
    def from_credentials(cls, credentials: credentials.Credentials):
        return cls(
            discovery.build('sqladmin',
                            'v1beta4',
                            credentials=credentials,
                            cache_discovery=False))

    def create_instance_sync(self,
                             project_id: str,
                             instance: str,
                             number_cpus: int = 1,
                             memory_size: str = 3840,
                             database_version: str = 'POSTGRES_9_6',
                             region: str = 'us-west1'):
        """Creates a new Google Cloud SQL instance and wait for provisioning.

        See https://cloud.google.com/sql/docs/postgres/create-instance for valid
        arguments.

        Args:
            project_id: The id of the project to provision the SQL instance in.
            instance: The name of the new instance being provisioned.
            number_cpus: The number of virtual CPUs to provision for the SQL
                instance.
            memory_size: The amount of memory, in MiB, to provision for the SQL
                instance.
            database_version: The type of database to provision.
            region: The geographic region to provision the SQL instance in.

        Raises:
            ValueError: for invalid argument combinations.
            DatabaseError: if unable to provision the SQL instance.
        """
        # See:
        # https://cloud.google.com/sql/docs/mysql/admin-api/v1beta4/instances
        if not (0 < number_cpus <= 64):
            raise ValueError('unexpected cpu count {!r}'.format(number_cpus))

        if not (3840 <= memory_size <= 425984):
            raise ValueError('unexpected memory size {!r}'.format(memory_size))

        tier = 'db-custom-{}-{}'.format(number_cpus, memory_size)
        database_instance_body = {
            'name': instance,
            'region': region,
            'databaseVersion': database_version,
            'settings': {
                'tier': tier,
                'backupConfiguration': {
                    'enabled': True
                }
            }
        }
        request = self._sqladmin_service.instances().insert(
            project=project_id, body=database_instance_body)

        # See
        # https://cloud.google.com/sql/docs/mysql/admin-api/v1beta4/instances/insert
        try:
            request.execute(num_retries=5)
        except errors.HttpError as e:
            if e.resp.status == 409:
                # A cloud SQL instance with the same name already exist. This is
                # fine because we can reuse this instance.
                return

        while True:
            request = self._sqladmin_service.instances().get(project=project_id,
                                                             instance=instance)
            response = request.execute(num_retries=5)
            # Response format:
            # https://cloud.google.com/sql/docs/mysql/admin-api/v1beta4/instances#resource
            if response['state'] == 'RUNNABLE':
                return
            elif response['state'] == 'PENDING_CREATE':
                time.sleep(2)
                continue
            else:
                raise DatabaseError(
                    'unexpected instance status after creation: {!r} [{!r}]'.
                    format(response['state'], response))

    def create_database_sync(self, project_id: str, instance: str,
                             database: str):
        """Creates a new database in a Cloud SQL instance and wait for completion.

        Args:
            project_id: The id of the project to create the database in.
            instance: The name of the instance to create the database in.
            database: The name of the new database to create.

        Raises:
            DatabaseError: if unable to create the new database.
        """
        # See:
        # https://cloud.google.com/sql/docs/mysql/admin-api/v1beta4/databases/insert
        request = self._sqladmin_service.databases().get(project=project_id,
                                                         instance=instance,
                                                         database=database)
        response = []
        try:
            response = request.execute(num_retries=5)
        except errors.HttpError as e:
            if e.resp.status == 404:
                # The database we would like to create does not exist yet. This
                # is what we want.
                pass
            else:
                raise DatabaseError(
                    ('Unexpected response when getting status of database '
                     '{!r}: [{!r}]').format(database, response))
        # This means the database already exist. In this case we do not need
        # to create the same database again.
        if 'name' in response:
            return
        request = self._sqladmin_service.databases().insert(project=project_id,
                                                            instance=instance,
                                                            body={
                                                                'instance':
                                                                instance,
                                                                'project':
                                                                project_id,
                                                                'name': database
                                                            })
        response = request.execute(num_retries=5)
        while response['status'] in ['PENDING']:
            request = self._sqladmin_service.databases().get(project=project_id,
                                                             instance=instance,
                                                             database=database)
            response = request.execute(num_retries=5)
            time.sleep(2)

        if response['status'] not in ['DONE', 'RUNNING']:
            raise DatabaseError(
                'unexpected database status after creation: {!r} [{!r}]'.format(
                    response['status'], response))

    def set_database_password(self, project_id: str, instance: str, user: str,
                              password: str):
        """Set the password for a database user.

        Args:
            project_id: The id of the project for the database user.
            instance: The name of the instance for the database user.
            user: The name of the database user e.g. "postgres".
            password: The new password to set.

        Raises:
            DatabaseError: if unable to set the new password.
        """
        # See:
        # https://cloud.google.com/sql/docs/mysql/admin-api/v1beta4/users/update

        request = self._sqladmin_service.users().update(
            project=project_id,
            instance=instance,
            host='no-host',
            name=user,
            body={'password': password})
        response = request.execute(num_retries=5)
        if response['status'] not in ['DONE', 'RUNNING']:
            raise DatabaseError(
                'unexpected database status after creation: {!r} [{!r}]'.format(
                    response['status'], response))

    @contextlib.contextmanager
    def with_cloud_sql_proxy(self,
                             project_id: str,
                             instance_name: str,
                             cloud_sql_proxy_path: Optional[str] = None,
                             region: str = 'us-west1',
                             port: int = 5432):
        """A context manager to run and kill cloud sql proxy subprocesses.

        Used to provides secure access to your Cloud SQL Second Generation
        instances without having to whitelist IP addresses or configure SSL.
        For more information:
        https://cloud.google.com/sql/docs/postgres/sql-proxy

        Args:
            project_id: GCP project id.
            instance_name: Name of the Cloud SQL instance cloud sql proxy
                targets at.
            cloud_sql_proxy_path: The command to run your cloud sql proxy.
            region: Where the Cloud SQL instance is in.
            port: The port your Postgres database is using. By default it is
                5432.

        Yields:
            None

        Raises:
            DatabaseError: If cloud sql proxy failed to start after 5 seconds.
        """
        db.close_old_connections()
        instance_connection_string = '{0}:{1}:{2}'.format(
            project_id, region, instance_name)
        instance_flag = '-instances={}=tcp:{}'.format(
            instance_connection_string, port)
        if cloud_sql_proxy_path is None:
            cloud_sql_proxy_path = shutil.which('cloud_sql_proxy')
            assert cloud_sql_proxy_path, 'could not find cloud_sql_proxy_path'
        process = popen_spawn.PopenSpawn([cloud_sql_proxy_path, instance_flag])
        try:
            # Make sure cloud sql proxy is started before doing the real work
            process.expect('Ready for new connections', timeout=60)
            yield
        except pexpect.exceptions.TIMEOUT:
            raise DatabaseError(
                ('Cloud SQL Proxy was unable to start after 60 seconds. Output '
                 'of cloud_sql_proxy: \n{}').format(process.before))
        except pexpect.exceptions.EOF:
            raise DatabaseError(
                ('Cloud SQL Proxy exited unexpectedly. Output of '
                 'cloud_sql_proxy: \n{}').format(process.before))
        finally:
            process.kill(signal.SIGTERM)

    def migrate_database(self,
                         project_dir: str,
                         project_id: str,
                         instance_name: str,
                         cloud_sql_proxy_path: str = 'cloud_sql_proxy',
                         region: str = 'us-west1',
                         port: Optional[int] = 5432):
        """Migrate to Cloud SQL database.

        This function should be called after we do the following:
            1. Generated the Django project source files.
            2. Setup Django environment so that it is using configuration files
               of the newly generated project.
            3. Created the Cloud SQL instance and database user.

        Args:
            project_dir: Absolute path of the Django project directory.
            project_id: GCP project id.
            instance_name: Name of the Cloud SQL instance where the database you
                want to migrate is in.
            cloud_sql_proxy_path: The command to run your cloud sql proxy.
            region: Where the Cloud SQL instance is in.
            port: The port being forwarded by cloud sql proxy.
        """
        with self.with_cloud_sql_proxy(project_id, instance_name,
                                       cloud_sql_proxy_path, region, port):
            try:
                # The environment variable must exist. This is the prerequisite
                # of calling this function
                settings_module = os.environ['DJANGO_SETTINGS_MODULE']

                # "makemigrations" will generate migration files based on
                # definitions in models.py.
                makemigrations_args = [
                    'django-admin', 'makemigrations',
                    '='.join(['--pythonpath', project_dir]),
                    '='.join(['--settings', settings_module])
                ]
                subprocess.check_call(makemigrations_args,
                                      stdout=subprocess.DEVNULL,
                                      stderr=subprocess.DEVNULL)
                # "migrate" will modify cloud sql database.
                migrate_args = [
                    'django-admin', 'migrate',
                    '='.join(['--pythonpath', project_dir]),
                    '='.join(['--settings', settings_module])
                ]
                subprocess.check_call(migrate_args,
                                      stdout=subprocess.DEVNULL,
                                      stderr=subprocess.DEVNULL)
            except Exception as e:
                raise crash_handling.UserError(
                    'Not able to migrate database.') from e

    def create_super_user(self,
                          superuser_name: str,
                          superuser_email: str,
                          superuser_password: str,
                          project_id: str,
                          instance_name: str,
                          cloud_sql_proxy_path: str = 'cloud_sql_proxy',
                          region: str = 'us-west1',
                          port: Optional[int] = 5432):
        """Create a super user in the cloud sql database.

        This function should be called after we did the following:
            1. Generated the Django project source files.
            2. Setup Django environment so that it is using configuration files
               of the newly generated project.
            3. Created the Cloud SQL instance and database user.
            4. Migrated database. Otherwise the schema for superuser does not
               exist.

        Args:
            superuser_name: Name of the super user you want to create.
            superuser_email: Email of the super user you want to create.
            superuser_password: Password of the super user you want to create.
            project_id: GCP project id.
            instance_name: The Cloud SQL instance name in which you want to
                create the super user.
            cloud_sql_proxy_path: The command to run your cloud sql proxy.
            region: Where the Cloud SQL instance is in.
            port: The port being forwarded by cloud sql proxy.
        """

        with self.with_cloud_sql_proxy(project_id, instance_name,
                                       cloud_sql_proxy_path, region, port):
            # This can only be imported after django.setup() is called
            try:
                from django.contrib.auth import get_user_model
                User = get_user_model()

                # Check whether the super user we want to create exist or not
                # If a superuser with the same name already exist, we will skip
                # creation
                users = User.objects.filter(username=superuser_name)
                for user in users:
                    if user.is_superuser:
                        return
                User.objects.create_superuser(username=superuser_name,
                                              email=superuser_email,
                                              password=superuser_password)
            except Exception as e:
                raise crash_handling.UserError(
                    'Not able to create super user.') from e
