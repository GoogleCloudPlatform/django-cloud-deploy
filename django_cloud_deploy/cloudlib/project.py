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
"""Manages Google Cloud Platform projects.

See https://gcloud-python.readthedocs.io/en/latest/resource-manager/api.html
"""

import subprocess

import backoff

from googleapiclient import discovery
from google.auth import credentials
from googleapiclient import errors


class ProjectError(Exception):
    """An exception occured while creating or accessing a project."""


class ProjectClient(object):
    """A class for managing Google Cloud Platform projects."""

    def __init__(self, cloudresourcemanager_service: discovery.Resource):
        self._cloudresourcemanager_service = cloudresourcemanager_service

    @classmethod
    def from_credentials(cls, credentials: credentials.Credentials):
        return cls(
            discovery.build(
                'cloudresourcemanager', 'v1', credentials=credentials))

    def project_exists(self, project_id: str) -> bool:
        """Returns True if the given project id exists."""
        request = self._cloudresourcemanager_service.projects().get(
            projectId=project_id)
        try:
            request.execute()
        except errors.HttpError as e:
            if e.resp.status in [403, 404]:
                return False
            raise
        return True

    def create_project(self, project_id: str, project_name: str):
        """Create a new GCP project."""
        request = self._cloudresourcemanager_service.projects().create(
            body={
                'name': project_name,
                'projectId': project_id,
            })
        response = request.execute()

        if 'name' not in response:
            raise ProjectError(
                'unexpected response creating project "{}": {}'.format(
                    project_id, response))

        self._confirm_project_creation(project_id)

    def create_and_set_project(self, project_id: str, project_name: str):
        self.create_project(project_id, project_name)
        self._set_gcloud_project(project_id)

    def set_existing_project(self, project_id: str):
        """Set an existing GCP project as the active project."""
        if self.project_exists(project_id):
            self._set_gcloud_project(project_id)
        else:
            raise ProjectError('project "{}" does not exist'.format(project_id))

    # The SLO is 30s at the 90th percentile:
    # https://cloud.google.com/resource-manager/reference/rest/v1/projects/create
    @backoff.on_predicate(backoff.constant, max_tries=20, interval=3)
    def _confirm_project_creation(self, project_id: str) -> bool:
        return self.project_exists(project_id)

    def _set_gcloud_project(self, project_id):
        # TODO: Remove this. This module (and the rest of the package)
        # should not be dependant on global state.
        command = ['gcloud', 'config', 'set', 'project', project_id]
        subprocess.check_call(command)
