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
"""Manages resources about static content serving of Django projects."""

import os
import pathlib

from django.conf import settings
from django.core import management
from django_cloud_deploy import crash_handling

from googleapiclient import discovery
from googleapiclient import errors
from googleapiclient import http
from google.auth import credentials


class StaticContentServeError(Exception):
    """An exception occured while managing resources about static content."""
    pass


class StaticContentServeClient(object):
    """A class for serving static contents for Django projects."""

    # All static files are supposed to be uploaded to
    # <bucket>/<GCS_ROOT>/<relative_path_with_local_static_content_directory>
    GCS_ROOT = 'static'

    def __init__(self, storage_service: discovery.Resource):
        self._storage_service = storage_service

    @classmethod
    def from_credentials(cls, credentials: credentials.Credentials):
        return cls(discovery.build('storage', 'v1', credentials=credentials))

    def _bucket_exist(self, project_id: str, bucket_name: str) -> bool:
        """Returns whether the given bucket exists under the given project.

        Args:
            project_id: Id of the GCP project.
            bucket_name: Name of the bucket.

        Returns:
           Whether the given bucket exists under the given project.

        Raises:
            StaticContentServeError: When it fails to list buckets under the
                given project.
        """
        request = self._storage_service.buckets().list(project=project_id)
        response = request.execute()
        if 'items' not in response:
            raise StaticContentServeError(
                'Unexpected response listing buckets in project "{}"'
                ': {}'.format(project_id, response))
        return any(item['name'] == bucket_name for item in response['items'])

    def create_bucket(self, project_id: str, bucket_name: str):
        """Create a Google Cloud Storage Bucket on the given project.

        Args:
            project_id: Id of the GCP project.
            bucket_name: Name of the bucket to create.

        Raises:
            StaticContentServeError: When it fails to create the bucket.
        """
        bucket_body = {'name': bucket_name}
        request = self._storage_service.buckets().insert(
            project=project_id, body=bucket_body)
        try:
            response = request.execute()
            # When the api call succeed, the response is a Bucket Resource
            # object. See
            # https://cloud.google.com/storage/docs/json_api/v1/buckets#resource
            if 'name' not in response:
                raise StaticContentServeError(
                    'Unexpected response creating bucket "{}" in project "{}"'
                    ': {}'.format(bucket_name, project_id, response))
        except errors.HttpError as e:
            if e.resp.status == 403:
                raise StaticContentServeError(
                    'You do not have permission to create bucket in project: '
                    '"{}"'.format(project_id))
            elif e.resp.status == 409:
                # A bucket with the given name already exist. But we don't know
                # whether that bucket exist under our GCP project or it exist
                # under somebody else's GCP project.
                # We will reuse the bucket if it exists under our GCP project.
                if self._bucket_exist(project_id, bucket_name):
                    return
                else:
                    raise StaticContentServeError(
                        'Bucket "{}" already exist. Name of the bucket should '
                        'be unique across the whole Google Cloud '
                        'Platform.'.format(bucket_name))
            else:
                raise StaticContentServeError(
                    'Unexpected error when creating bucket "{}" in project "{}"'
                    .format(bucket_name, project_id)) from e

    def make_bucket_public(self, bucket_name: str):
        """Make a Google Cloud Storage Bucket public readable.

        This step is necessary to serve static content.

        Args:
            bucket_name: Name of the bucket to create.

        Raises:
            StaticContentServeError: When it fails to make the bucket public.
        """
        request = self._storage_service.buckets().getIamPolicy(
            bucket=bucket_name)
        try:
            response = request.execute()
            if 'bindings' not in response:
                raise StaticContentServeError(
                    'Unexpected responses getting iam policy of bucket "{}"'.
                    format(bucket_name))
        except errors.HttpError as e:
            if e.resp.status == 403:
                raise StaticContentServeError(
                    ('You do not have permission to get iam policy of bucket '
                     '"{}"').format(bucket_name))
            elif e.resp.status == 404:
                raise StaticContentServeError(
                    'Bucket "{}" not found.'.format(bucket_name))
            else:
                raise StaticContentServeError(
                    'Unexpected error getting iam policy of bucket "{}"'.format(
                        bucket_name)) from e

        bindings = response['bindings']
        new_binding = {
            'role': 'roles/storage.objectViewer',
            'members': ['allUsers']
        }
        bindings.append(new_binding)
        body = {'bindings': bindings}
        request = self._storage_service.buckets().setIamPolicy(
            bucket=bucket_name, body=body)
        try:
            response = request.execute()
            if 'bindings' not in response:
                raise StaticContentServeError(
                    'Unexpected responses setting iam policy of bucket "{}"'.
                    format(bucket_name))
        except errors.HttpError as e:
            if e.resp.status == 403:
                raise StaticContentServeError(
                    ('You do not have permission to set iam policy of bucket '
                     '"{}"').format(bucket_name))
            elif e.resp.status == 404:
                raise StaticContentServeError(
                    'Bucket "{}" not found.'.format(bucket_name))
            else:
                raise StaticContentServeError(
                    'Unexpected error setting iam policy of bucket "{}"'.format(
                        bucket_name)) from e

    def _upload_file_to_object(self, local_file_path: str, bucket_name: str,
                               object_name: str):
        """Upload the contents of a local file to an object in a GCS bucket."""
        media_body = http.MediaFileUpload(local_file_path)
        body = {'name': object_name}
        request = self._storage_service.objects().insert(
            bucket=bucket_name, body=body, media_body=media_body)
        try:
            response = request.execute()
            if 'name' not in response:
                raise StaticContentServeError(
                    'Unexpected responses when uploading file "{}" to '
                    'bucket "{}"'.format(local_file_path, bucket_name))
        except errors.HttpError as e:
            if e.resp.status == 403:
                raise StaticContentServeError(
                    'You do not have permission to upload files to '
                    'bucket "{}"'.format(bucket_name))
            elif e.resp.status == 404:
                raise StaticContentServeError(
                    'Bucket "{}" not found.'.format(bucket_name))
            else:
                raise StaticContentServeError(
                    'Unexpected error when uploading file "{}" to '
                    'bucket "{}"'.format(local_file_path, bucket_name)) from e

        # http.MediaFileUpload opens a file but never closes it. So we
        # need to manually close the file to avoid "ResourceWarning:
        # unclosed file".
        # TODO: Remove this line when
        # https://github.com/googleapis/google-api-python-client/issues/575
        # is resolved.
        media_body.stream().close()

    def upload_content(self,
                       bucket_name: str,
                       static_content_dir: str,
                       gcs_folder_root: str = None):
        """Upload content in the given directory to a GCS bucket.

        Args:
            bucket_name: Name of the bucket you want to upload static content
                to.
            static_content_dir: Absolute path of the directory containing
                static files of the Django app.
            gcs_folder_root: Name of root folder for files in GCS bucket.

        Raises:
            StaticContentServeError: When failed to upload files.
        """

        prefix_length = len(static_content_dir)

        # The api only supports uploading a single file. So we need to iterate
        # all files in the given directory.
        for directory_absolute_path, _, files in os.walk(static_content_dir):
            directory_relative_path = os.path.relpath(directory_absolute_path,
                                                      static_content_dir)
            for filename in files:
                gcs_folder_root = gcs_folder_root or self.GCS_ROOT
                # Path of the file in the GCS bucket. Always use POSIX paths
                # to avoid backslashes in names when running on Windows.
                gcs_relative_path = pathlib.PurePosixPath(
                    directory_relative_path.replace('\\', '/'))
                gcs_object_path = (
                    pathlib.PurePosixPath(gcs_folder_root) / gcs_relative_path /
                    pathlib.PurePosixPath(filename))

                # Local absolute path of the file
                local_file_path = os.path.join(directory_absolute_path,
                                               filename)
                self._upload_file_to_object(local_file_path, bucket_name,
                                            str(gcs_object_path))

    def collect_static_content(self):
        """Collect static content of the provided Django project.

        This function should be called only after django.setup() is called.

        Raises:
            StaticContentServeError: If Django environment is not correctly
                setup.
        """

        if not settings.configured:
            raise StaticContentServeError(
                'Django environment is not setup correctly or the settings '
                'module is invalid. We cannot collect static files.')
        cwd = os.getcwd()
        # Change directory to the Django project directory. If we do not do
        # this, static content will be collected in your current directory.
        # This is not expected.
        os.chdir(settings.BASE_DIR)
        try:
            management.call_command(
                'collectstatic', verbosity=0, interactive=False)
        except Exception as e:
            raise crash_handling.UserError(
                'Not able to collect static files.') from e
        finally:
            os.chdir(cwd)
