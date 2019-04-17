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
"""Manages Cloud Source Repositories.

See https://cloud.google.com/source-repositories/
"""

from typing import Any, Dict, List

from googleapiclient import discovery
from googleapiclient import errors
from google.auth import credentials


class CloudSourceRepositoryError(Exception):
    pass


class CloudSourceRepositoryClient(object):
    """A class for managing cloud source repositories."""

    def __init__(self, cloudsource_service: discovery.Resource):
        self._cloudsource_service = cloudsource_service

    @classmethod
    def from_credentials(cls, credentials: credentials.Credentials):
        return cls(
            discovery.build('sourcerepo',
                            'v1',
                            credentials=credentials,
                            cache_discovery=False))

    def list_repos(self, project_id: str) -> List[Dict[str, Any]]:
        """List cloud source repositories under the given project.

        Args:
            project_id: GCP project id.

        Returns:
            A list for cloud source repositories in the following format:
                [
                    {
                        "name": "projects/<project_id>/repos/<repo_name>",
                        "url": <cloud_source_repo_url>,
                        "mirrorConfig": {
                            "url": <github_url>
                        }
                    },
                ]
        Raises:
            CloudSourceRepositoryError: If failed when calling the api for
                listing cloud source repositories.
        """
        resource_name = 'projects/{}'.format(project_id)
        request = self._cloudsource_service.projects().repos().list(
            name=resource_name)
        try:
            response = request.execute(num_retries=5)
            return response.get('repos', [])
        except errors.HttpError as e:
            raise CloudSourceRepositoryError(
                'Failed to list cloud source repositories') from e
