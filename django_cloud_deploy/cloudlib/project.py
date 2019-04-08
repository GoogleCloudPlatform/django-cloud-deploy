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

from typing import Any, Dict, List

import backoff
import google_auth_httplib2

from googleapiclient import discovery
from googleapiclient import http
from google.auth import credentials
from googleapiclient import errors

# After 2018/10/01, when a Googler created a new cloud project in google.com,
# the new project is required to be created in a folder. For most Googlers,
# there will be only one folder option named “google_default”. This is the id
# of that folder.
_DEFAULT_GOOGLE_FOLDER_ID = '396521612403'
_GOOGLE_ORGANIZATION_ID = '433637338589'  # id of organization "google.com"


class ProjectError(Exception):
    """An error occurred while creating or accessing a project."""


class ProjectExistsError(ProjectError):
    """Attempted to create a project that already exists."""


class ProjectClient(object):
    """A class for managing Google Cloud Platform projects."""

    def __init__(self, cloudresourcemanager_service: discovery.Resource):
        self._cloudresourcemanager_service = cloudresourcemanager_service

    @classmethod
    def from_credentials(cls, credentials: credentials.Credentials):
        http_client = http.set_user_agent(http.build_http(),
                                          'django-cloud-deploy')
        auth_http = google_auth_httplib2.AuthorizedHttp(credentials,
                                                        http=http_client)
        return cls(
            discovery.build('cloudresourcemanager',
                            'v1',
                            http=auth_http,
                            cache_discovery=False))

    def project_exists(self, project_id: str) -> bool:
        """Returns True if the given project id exists."""
        try:
            self.get_project(project_id)
        except errors.HttpError as e:
            if e.resp.status in [403, 404]:
                return False
            raise
        return True

    def get_project(self, project_id: str) -> Dict[str, Any]:
        """Returns True if the given project id exists."""
        request = self._cloudresourcemanager_service.projects().get(
            projectId=project_id)
        try:
            return request.execute(num_retries=5)
        except errors.HttpError as e:
            raise e

    def get_project_permissions(self, project_id: str) -> List[Dict[str, Any]]:
        """Returns a list of permissions from the project"""
        request = self._cloudresourcemanager_service.projects().getIamPolicy(
            resource=project_id, body={})
        try:
            response = request.execute(num_retries=5)
            return response.get('bindings', [])
        except errors.HttpError as e:
            if e.resp.status in [403, 404]:
                return []

    def _is_google_account(self) -> bool:
        """Returns whether the user logged in with a google.com account."""
        body = {'filter': 'domain:google.com'}
        request = self._cloudresourcemanager_service.organizations().search(
            body=body)
        response = request.execute(num_retries=5)

        # If we have non-empty result, then we are sure the user has access to
        # 'google.com' organization
        return 'organizations' in response

    def create_project(self, project_id: str, project_name: str):
        """Create a new GCP project."""
        body = {
            'name': project_name,
            'projectId': project_id,
        }

        if self._is_google_account():
            body['parent'] = {'id': _DEFAULT_GOOGLE_FOLDER_ID, 'type': 'folder'}

        request = self._cloudresourcemanager_service.projects().create(
            body=body)
        try:
            response = request.execute(num_retries=5)
        except errors.HttpError as e:
            if e.resp.status == 409:
                raise ProjectExistsError(
                    'the project "{}" already exists'.format(project_id)) from e
            raise

        if 'name' not in response:
            raise ProjectError(
                'unexpected response creating project "{}": {}'.format(
                    project_id, response))

        if not self._confirm_project_creation(project_id):
            raise ProjectError(
                'Project "{}" is not successfully created.'.format(project_id))

    # The SLO is 30s at the 90th percentile:
    # https://cloud.google.com/resource-manager/reference/rest/v1/projects/create
    @backoff.on_predicate(backoff.constant,
                          max_tries=20,
                          interval=3,
                          logger=None)
    def _confirm_project_creation(self, project_id: str) -> bool:
        return self.project_exists(project_id)
