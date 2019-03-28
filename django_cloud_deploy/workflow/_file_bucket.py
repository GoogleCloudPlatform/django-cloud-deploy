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
"""Workflow for creating the bucket used for file uploads."""

from django_cloud_deploy.cloudlib import static_content_serve

from google.auth import credentials


class FileBucketCreationWorkflow(object):
    """A class to control the workflow of serving static content."""

    def __init__(self, credentials: credentials.Credentials):
        self._static_content_serve_client = (
            static_content_serve.StaticContentServeClient.from_credentials(
                credentials))

    def create_file_bucket(self, project_id: str, bucket_name: str):
        """Create bucket and assign correct permissions.

        The public Google Cloud Storage Bucket will hold files uploaded to the
        Django app.

        Args:
            project_id: Id of GCP project.
            bucket_name: Name of the Google Cloud Storage Bucket
                used to store files by the Django app. By default it is equal to
                files-project id.
        """

        self._static_content_serve_client.create_bucket(project_id, bucket_name)
