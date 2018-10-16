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

import time

from google.auth import credentials
from googleapiclient import discovery


class DatabaseError(Exception):
    pass


class DatabaseClient(object):
    """A class for managing Google Cloud SQL objects."""

    def __init__(self, sqladmin_service: discovery.Resource):
        self._sqladmin_service = sqladmin_service

    @classmethod
    def from_credentials(cls, credentials: credentials.Credentials):
        return cls(
            discovery.build('sqladmin', 'v1beta4', credentials=credentials))

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
                "backupConfiguration": {
                    "enabled": True
                }
            }
        }
        request = self._sqladmin_service.instances().insert(
            project=project_id, body=database_instance_body)

        # See
        # https://cloud.google.com/sql/docs/mysql/admin-api/v1beta4/instances/insert
        request.execute()

        while True:
            request = self._sqladmin_service.instances().get(
                project=project_id, instance=instance)
            response = request.execute()
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
        request = self._sqladmin_service.databases().insert(
            project=project_id,
            instance=instance,
            body={
                'instance': instance,
                'project': project_id,
                'name': database
            })
        response = request.execute()
        while response['status'] in ['PENDING']:
            request = self._sqladmin_service.databases().get(
                project=project_id, instance=instance, database=database)
            response = request.execute()
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
        response = request.execute()
        if response['status'] not in ['DONE', 'RUNNING']:
            raise DatabaseError(
                'unexpected database status after creation: {!r} [{!r}]'.format(
                    response['status'], response))
