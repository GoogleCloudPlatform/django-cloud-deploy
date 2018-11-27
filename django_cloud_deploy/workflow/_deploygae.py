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

import pexpect


class DeployNewAppError(Exception):
    """A class to control the workflow for deploying an Django app to GAE."""


class DeploygaeWorkflow(object):
    """Workflow to deploy Django app on GAE."""

    def deploy_gae_app(self,
                       project_id: str,
                       django_directory_path: str,
                       region: str = 'us-west2') -> str:
        """Uses Gcloud SDK to upload to GAE.

        Args:
            project_id: GCP project id to use.
            django_directory_path: Path where the django source files are
                located.
            region: Region to deploy the django app.

        Raises:
            DeployNewAppError: If unable to deploy the app.

        Returns:
            The url of the deployed Django app.
        """

        app_yaml_path = os.path.join(django_directory_path, 'app.yaml')
        project = '--project={}'.format(project_id)
        args = ['app', 'deploy', app_yaml_path, project]
        process = pexpect.spawn('gcloud', args)
        try:
            index = process.expect(
                ['\[{}\]\s*{}'.format(i, region) for i in range(1, 10)])
            process.sendline(str(index))
            process.expect('Do you want to continue (Y/n)?')
            process.sendline('Y')
            process.expect('Deployed service', timeout=600)  # 10 Min Timeout
        except (pexpect.exceptions.TIMEOUT, pexpect.exceptions.EOF):
            raise DeployNewAppError(
                ('Error occured when trying to deploy GAE application. Output '
                 'of process: \n{}').format(process.before))
        finally:
            process.close()
        return 'https://{}.appspot.com/'.format(project_id)
