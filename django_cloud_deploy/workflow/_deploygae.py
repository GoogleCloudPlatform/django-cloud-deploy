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
"""Workflow for deploying a Django app to GAE."""

import os
import shutil
import subprocess
import time
from typing import Any, Dict

import backoff
from googleapiclient import discovery
import yaml

from google.auth import credentials


class DeployNewAppError(Exception):
    """A class to control the workflow for deploying an Django app to GAE."""


class DeploygaeWorkflow(object):
    """Workflow to deploy Django app on GAE."""

    def __init__(self, credentials: credentials.Credentials):
        self._appengine_service = discovery.build('appengine',
                                                  'v1',
                                                  credentials=credentials,
                                                  cache_discovery=False)

    def _create_app(self, project_id: str, region: str):
        """Synchronously create an App Engine application in the project."""
        create_response = self._appengine_service.apps().create(
            body={
                'id': project_id,
                'locationId': region
            }).execute()

        # The creation response will be reference to an on-going operation.
        # Pool the operation until it is complete or returns an error. See:
        # https://cloud.google.com/appengine/docs/admin-api/creating-an-application
        operation_id = create_response['name'].split('/')[-1]
        while True:
            operation = self._appengine_service.apps().operations().get(
                appsId=project_id, operationsId=operation_id).execute()
            if 'error' in operation:
                raise DeployNewAppError(
                    'Failed to create App Engine app: {}'.format(
                        operation['error']))
            elif operation.get('done'):
                break
            time.sleep(2)

    @staticmethod
    @backoff.on_predicate(
        backoff.expo, lambda x: x.returncode != 0, max_tries=5)
    def _app_deploy_with_retry(gcloud_path: str, project: str,
                               app_yaml_path: str, env_vars: Dict[str, Any]
                              ) -> subprocess.CompletedProcess:
        """Run 'gcloud app deploy' with retries.

        Args:
            gcloud_path: The path of your gcloud cli tool.
            project: GCP project id.
            app_yaml_path: Absolute path of your app.yaml.
            env_vars: A dictionary of the environment variables.

        Returns:
            The result of the subprocess run.
        """
        gcloud_result = subprocess.run(
            [gcloud_path, '-q', project, 'app', 'deploy', app_yaml_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            env=env_vars)
        return gcloud_result

    def deploy_gae_app(self,
                       project_id: str,
                       django_directory_path: str,
                       region: str = 'us-west2',
                       is_new: bool = True) -> str:
        """Uses Gcloud SDK to upload to GAE.

        Args:
            project_id: GCP project id to use.
            django_directory_path: Path where the django source files are
                located.
            region: Region to deploy the django app.
            is_new: Flag to indicate if deploying an new app.

        Raises:
            DeployNewAppError: If unable to deploy the app.

        Returns:
            The url of the deployed Django app.
        """

        if is_new:
            self._create_app(project_id, region)

        gcloud_path = shutil.which('gcloud')
        assert gcloud_path, 'could not find gcloud'

        app_yaml_path = os.path.join(django_directory_path, 'app.yaml')
        project = '--project={}'.format(project_id)

        # We need to grab all environment variables to pass to the subprocess
        env_vars = dict(os.environ)
        env_vars['CLOUDSDK_METRICS_ENVIRONMENT'] = 'django-cloud-deploy'
        gcloud_result = self._app_deploy_with_retry(gcloud_path, project,
                                                    app_yaml_path, env_vars)
        if gcloud_result.returncode != 0:
            raise DeployNewAppError(gcloud_result.stderr)

        with open(app_yaml_path) as yaml_file:
            attributes = yaml.load(yaml_file.read(), Loader=yaml.FullLoader)
        service_name = attributes.get('service')

        # This is the name of the default service. This case happens in real
        # use cases.
        if service_name == 'default':
            return 'https://{}.appspot.com/'.format(project_id)
        else:  # This case happens in test
            return 'https://{}-dot-{}.appspot.com'.format(
                service_name, project_id)
