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

import time

from googleapiclient import discovery
from googleapiclient import errors
from google.auth import credentials

from django_cloud_deploy import crash_handling


class EnableServiceError(Exception):
    pass


class EnableServiceClient(object):
    """A class for enabling GCP apis."""

    def __init__(self, service_usage_service: discovery.Resource):
        self._service_usage_service = service_usage_service

    @classmethod
    def from_credentials(cls, credentials: credentials.Credentials):
        return cls(
            discovery.build('serviceusage',
                            'v1',
                            credentials=credentials,
                            cache_discovery=False))

    def enable_service_sync(self, project_id: str, service: str):
        """Enable a service for the given project.

        Args:
            project_id: GCP project id.
            service: Name of the service to be enabled. For example,
                "drive.googleapis.com"

        Raises:
            EnableServiceError: When it fails to enable a service.
        """

        service_name = '/'.join(['projects', project_id, 'services', service])
        request = self._service_usage_service.services().enable(
            name=service_name)
        try:
            response = request.execute(num_retries=5)
        except errors.HttpError as e:
            if e.resp.status == 400:
                tos = 'terms of service'
                if tos in str(e):
                    url = 'https://console.developers.google.com/terms/cloud'
                    msg = ('Please accept the terms of service in the Google'
                           'Cloud Console @ {}'.format(url))
                    raise crash_handling.UserError(msg)
            # For all errors that are not related to ToS we want to raise
            raise e

        # When the api call succeed, the response is a Service object.
        # See
        # https://cloud.google.com/service-usage/docs/reference/rest/v1/services/get
        if 'name' not in response:
            raise EnableServiceError(
                'unexpected response enabling service "{}": {}'.format(
                    service_name, response))

        while True:
            request = self._service_usage_service.services().get(
                name=service_name)
            response = request.execute(num_retries=5)
            # Response format:
            # https://cloud.google.com/service-usage/docs/reference/rest/v1/Service
            if response['state'] == 'ENABLED':
                return
            elif response['state'] == 'DISABLED':
                time.sleep(2)
                continue
            else:
                # In 'STATE_UNSPECIFIED' state.
                raise EnableServiceError(
                    'unexpected service status after enabling: {!r}: [{!r}]'.
                    format(response['status'], response))
