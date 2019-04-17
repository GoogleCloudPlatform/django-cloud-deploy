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
"""Manages Cloud Build Triggers.

See https://cloud.google.com/cloud-build/docs/running-builds/automate-builds
"""

from typing import Dict

from googleapiclient import discovery
from googleapiclient import errors
from google.auth import credentials


class CloudBuildError(Exception):
    pass


class CloudBuildClient(object):
    """A class for managing cloud build triggers."""

    _DESCRIPTION = ('Cloud Build Trigger automatically created by Django Cloud '
                    'Deploy')

    def __init__(self, cloudbuild_service: discovery.Resource):
        self._cloudbuild_service = cloudbuild_service

    @classmethod
    def from_credentials(cls, credentials: credentials.Credentials):
        return cls(
            discovery.build('cloudbuild',
                            'v1',
                            credentials=credentials,
                            cache_discovery=False))

    def create_trigger(self,
                       project_id: str,
                       repo_name: str,
                       branch_regexp: str,
                       env_vars: Dict[str, str] = None):
        """Create a Cloud Build Trigger.

        Args:
            project_id: GCP project id.
            repo_name: The Github repo name shown on cloud source. It should
                have the format "github_<account_name>_<repo_name>". For
                example, "github_googlecloudplatform_django-cloud-deploy"
            branch_regexp: A regular expression to control which branches can
                trigger the build. For example, a branch_regexp equals to ".*"
                will trigger builds when developer pushes to all branches.
            env_vars: A dictionary of environment variables to be used in
                the cloud build environment.
        """
        request_body = {
            'triggerTemplate': {
                'projectId': project_id,
                'repoName': repo_name,
                'branchName': branch_regexp,
            },
            'description': self._DESCRIPTION,
            'filename': 'cloudbuild.yaml',
            'substitutions': env_vars if env_vars else {}
        }
        request = self._cloudbuild_service.projects().triggers().create(
            projectId=project_id, body=request_body)
        try:
            request.execute(num_retries=5)
        except errors.HttpError as e:
            raise CloudBuildError(
                'Failed to create the cloud build trigger') from e
