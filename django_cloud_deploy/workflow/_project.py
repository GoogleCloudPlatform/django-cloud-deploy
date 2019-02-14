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
"""Manages Google Cloud Platform projects creation."""

import enum

from django_cloud_deploy.cloudlib import project

from google.auth import credentials


class CreationMode(enum.Enum):
    CREATE = 1
    CREATE_IF_NEEDED = 2
    MUST_EXIST = 3  # Useful for e2e tests.


class ProjectionCreationError(Exception):
    """An exception raised when project creation failed."""


class ProjectExistsError(ProjectionCreationError):
    """Attempted to create a project that already exists."""


class ProjectWorkflow(object):
    """A class for managing Google Cloud Platform projects."""

    def __init__(self, credentials: credentials.Credentials):
        self._project_client = project.ProjectClient.from_credentials(
            credentials)

    def create_project(
            self,
            project_name: str,
            project_id: str,
            project_creation: CreationMode = CreationMode.CREATE_IF_NEEDED):
        """Create a GCP Project and set it to be the active project of gcloud.

        Args:
            project_name: Name of the GCP project the caller wants to create.
            project_id: Id of the GCP project to create.
            project_creation: Whether we want to create the GCP project or use
                an existing project.

        Returns:
            The project id of the created project.

        Raises:
            ProjectionCreationError: If we want to create the project and the
                project already exists, or we only want to set the project to be
                the active project of gcloud but the project does not exist.
        """

        exists = self._project_client.project_exists(project_id)
        if exists:
            if project_creation == CreationMode.CREATE:
                raise ProjectExistsError(
                    'project {!r} already exists'.format(project_id))
        else:
            if project_creation == CreationMode.MUST_EXIST:
                raise ProjectionCreationError(
                    'project {!r} does not exist'.format(project_id))
            else:
                self._project_client.create_project(project_id, project_name)
