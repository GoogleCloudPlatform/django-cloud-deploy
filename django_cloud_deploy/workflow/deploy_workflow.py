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
"""Workflow to to fork between GKE and GAE."""

from typing import Dict

from django_cloud_deploy.workflow import _deploygae
from django_cloud_deploy.workflow import _deploygke


class DeployWorkflow(object):
    """Workflow to to fork between GKE and GAE."""

    def __init__(self, credentials):
        self.credentials = credentials

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
        workflow = _deploygae.DeploygaeWorkflow(self.credentials)
        return workflow.deploy_gae_app(project_id, django_directory_path,
                                       region, is_new)

    def deploy_gke_app(self,
                       project_id: str,
                       cluster_name: str,
                       app_directory: str,
                       app_name: str,
                       image_name: str,
                       secrets: Dict[str, Dict[str, str]],
                       region: str = 'us-west1',
                       zone: str = 'us-west1-a') -> str:
        """Deploy a Django app to gke.

        Args:
            project_id: GCP project id.
            cluster_name: Name of the cluster to host the app.
            app_directory: Absolute path of the directory of your Django app.
            app_name: Name of the Django app.
            image_name: Tag of the docker image of the app.
            secrets: Secrets necessary to run the app.
            region: Where do you want to host the cluster.
            zone: Name of the Google Compute Engine zone in which the cluster
                resides.

        Raises:
            DeployNewAppError: If unable to deploy the app.

        Returns:
            The url of the deployed Django app.
        """
        workflow = _deploygke.DeploygkeWorkflow(self.credentials)
        return workflow.deploy_new_app_sync(project_id, cluster_name,
                                            app_directory, app_name, image_name,
                                            secrets, region, zone)

    def update_gke_app(self,
                       project_id: str,
                       cluster_name: str,
                       app_directory: str,
                       app_name: str,
                       image_name: str,
                       zone: str = 'us-west1-a') -> str:
        """Update an existing Django app on gke.

        Args:
            project_id: GCP project id.
            cluster_name: Name of the cluster to host the app.
            app_directory: Absolute path of the directory of your Django app.
            app_name: Name of the Django app.
            image_name: Tag of the docker image of the app.
            zone: Name of the Google Compute Engine zone in which the cluster
                resides.

        Raises:
            DeployNewAppError: If unable to deploy the app.

        Returns:
            The url of the deployed Django app.
        """
        workflow = _deploygke.DeploygkeWorkflow(self.credentials)
        return workflow.update_app_sync(project_id, cluster_name, app_directory,
                                        app_name, image_name, zone)
