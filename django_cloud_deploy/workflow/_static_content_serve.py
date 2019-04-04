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
"""Workflow for serving static content of Django projects."""

from django_cloud_deploy.cloudlib import static_content_serve

from google.auth import credentials


class StaticContentServeWorkflow(object):
    """A class to control the workflow of serving static content."""

    def __init__(self, credentials: credentials.Credentials):
        self._static_content_serve_client = (
            static_content_serve.StaticContentServeClient.from_credentials(
                credentials))

    def serve_static_content(self, project_id: str, bucket_name: str,
                             static_content_dir: str):
        """Do all the work for serving static content of the provided project.

        The static content is served with a public Google Cloud Storage Bucket.

        Args:
            project_id: Id of GCP project.
            bucket_name: Name of the bucket to create and serve static content.
            static_content_dir: Absolute path of the directory for static
                content.
        """

        self._static_content_serve_client.collect_static_content()
        self._static_content_serve_client.create_bucket(project_id, bucket_name)
        self._static_content_serve_client.make_bucket_public(bucket_name)
        self._static_content_serve_client.upload_content(
            bucket_name, static_content_dir)

    def set_cors_policy(self, bucket_name: str, origin: str):
        self._static_content_serve_client.set_cors_policy(bucket_name, origin)

    def serve_secret_content(self, project_id: str, bucket_name: str,
                             secrec_content_dir: str):
        """Do all the work for serving secret content of the provided project.

        The secret content is served with a Google Cloud Storage Bucket.

        Args:
            project_id: Id of GCP project.
            bucket_name: Name of the bucket to create and serve secret content.
            secrec_content_dir: Absolute path of the directory for secret
                content.
        """

        self._static_content_serve_client.create_bucket(project_id, bucket_name)
        self._static_content_serve_client.upload_content(
            bucket_name, secrec_content_dir, gcs_folder_root='secrets')

    def update_static_content(self, bucket_name: str, static_content_dir: str):
        """Update GCS bucket after user modified the Django app.

        Args:
            bucket_name: Name of the bucket to create and serve static content.
            static_content_dir: Absolute path of the directory for static
                content.
        """
        self._static_content_serve_client.collect_static_content()
        self._static_content_serve_client.upload_content(
            bucket_name, static_content_dir)
