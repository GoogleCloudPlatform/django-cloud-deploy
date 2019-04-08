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
"""Workflow for managing database of the Django app."""

from typing import Callable, Optional

from django_cloud_deploy.cloudlib import database

from google.auth import credentials


class DatabaseWorkflow(object):
    """A class to control workflow for setting up the database for a Django app.
    """

    def __init__(self, credentials: credentials.Credentials):
        self._database_client = database.DatabaseClient.from_credentials(
            credentials)

    def create_and_setup_database(self,
                                  project_dir: str,
                                  project_id: str,
                                  instance_name: str,
                                  database_name: str,
                                  database_password: str,
                                  superuser_name: str,
                                  superuser_email: str,
                                  superuser_password: str,
                                  database_user: str = 'postgres',
                                  cloud_sql_proxy_path: str = 'cloud_sql_proxy',
                                  region: str = 'us-west1',
                                  port: Optional[int] = 5432):
        """Create a cloud database and set password for default user.

        Follows the steps found @
        https://cloud.google.com/python/django/kubernetes-engine

        regarding setting up a database.

        Args:
            project_dir: Absolute path of the Django project directory.
            project_id: GCP project id.
            instance_name: The Cloud SQL instance name in which you want to
                    create the super user.
            database_name: The name of the new database to create.
            database_password: The new password to set.
            superuser_name: Name of the super user you want to create.
            superuser_email: Email of the super user you want to create.
            superuser_password: Password of the super user you want to create.
            database_user: The name of the database user. By default it is
                    "postgres".
            cloud_sql_proxy_path: The command to run your cloud sql proxy.
            region: Where the Cloud SQL instance is in.
            port: The port being forwarded by cloud sql proxy.
        """

        self._database_client.create_instance_sync(project_id, instance_name)
        self._database_client.create_database_sync(project_id, instance_name,
                                                   database_name)
        self._database_client.set_database_password(project_id, instance_name,
                                                    database_user,
                                                    database_password)
        self._database_client.migrate_database(project_dir, project_id,
                                               instance_name,
                                               cloud_sql_proxy_path, region,
                                               port)
        self._database_client.create_super_user(superuser_name, superuser_email,
                                                superuser_password, project_id,
                                                instance_name,
                                                cloud_sql_proxy_path, region,
                                                port)

    def migrate_database(self,
                         project_dir: str,
                         project_id: str,
                         instance_name: str,
                         cloud_sql_proxy_path: str = 'cloud_sql_proxy',
                         region: str = 'us-west1',
                         port: Optional[int] = 5432):
        """Migrate to Cloud SQL database.

        This function is useful for updating a deployed Django app. It should be
        called after we did the following:
            1. Generated the Django project source files.
            2. Setup Django environment so that it is using configuration files
                 of the newly generated project.
            3. Created the Cloud SQL instance and database user.

        Args:
            project_dir: Absolute path of the Django project directory.
            project_id: GCP project id.
            instance_name: The Cloud SQL instance name in which you want to
                    create the super user.
            cloud_sql_proxy_path: The command to run your cloud sql proxy.
            region: Where the Cloud SQL instance is in.
            port: The port being forwarded by cloud sql proxy.
        """
        self._database_client.migrate_database(project_dir, project_id,
                                               instance_name,
                                               cloud_sql_proxy_path, region,
                                               port)

    def with_cloud_sql_proxy(self,
                             project_id: str,
                             instance_name: str,
                             cloud_sql_proxy_path: str = 'cloud_sql_proxy',
                             region: str = 'us-west1',
                             port: int = 5432) -> Callable:
        """A wrapper for database_client.with_cloud_sql_proxy.

        This method is useful in integration tests to check whether cloud
        database has expected contents. For example, whether superuser is
        created.

        Args:
            project_id: GCP project id.
            instance_name: The Cloud SQL instance name in which you want to
                create the super user.
            cloud_sql_proxy_path: The command to run your cloud sql proxy.
            region: Where the Cloud SQL instance is in.
            port: The port your Postgres database is using. By default it is
                5432.
        Returns:
            A context manager to run and kill cloud sql proxy subprocess.
        """
        return self._database_client.with_cloud_sql_proxy(
            project_id, instance_name, cloud_sql_proxy_path, region, port)
