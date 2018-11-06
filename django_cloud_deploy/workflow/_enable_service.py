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
"""Manages Google Cloud Services."""

import json
import os
from typing import Dict
from typing import List

from django_cloud_deploy.cloudlib import enable_service

from google.auth import credentials


class EnableServiceWorkflow(object):
    """A class to control the workflow for enabling all required services."""

    def __init__(self, credentials: credentials.Credentials):
        self._enable_service_client = (
            enable_service.EnableServiceClient.from_credentials(credentials))

    def enable_required_services(self,
                                 project_id: str,
                                 services: List[Dict[str, str]] = None):
        """Enable required services for deploying Django apps to GKE.

        Args:
            project_id: The GCP project id to enable services.
            services: The services to be enabled. It should have the following
                format:
                    [
                        {
                            "title": "Compute Engine API",
                            "name": "compute.googleapis.com"
                        },
                    ]
        """

        services = services or EnableServiceWorkflow.load_services()
        for service in services:
            self._enable_service_client.enable_service_sync(
                project_id, service['name'])

    @staticmethod
    def load_services() -> List[Dict[str, str]]:
        """Load information of the services to enable from a json file.

        Returns:
            A list of the services to be enabled.
        """

        data_dir = os.path.join(os.path.dirname(__file__), 'data')
        data_file_path = os.path.join(data_dir, 'services.json')
        with open(data_file_path) as data_file:
            services = json.load(data_file)
        return services
