# Copyright 2018 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for the cloudlib.static_content_serve module."""

import os
import tempfile

from absl.testing import absltest
from django_cloud_deploy.cloudlib import static_content_serve
from django_cloud_deploy.cloudlib.tests.lib import http_fake
from googleapiclient import errors

PROJECT_ID = 'fake_project_id'
BUCKET_NAME = 'fake_bucket_name'

POLICY = {'entity': 'allUsers', 'role': 'READER'}


class BucketAccessControlsFake(object):
    """A fake object returned by ...bucketAccessControls()."""

    def __init__(self):
        self.policy = {}

    def patch(self, bucket, entity, body):
        if 'no_permission' in bucket:
            return http_fake.HttpRequestFake(
                errors.HttpError(
                    http_fake.HttpResponseFake(403), b'permission denied'))
        elif 'invalid' in bucket:
            return http_fake.HttpRequestFake({'invalid': 'response'})
        else:
            new_policy = {'entity': entity, 'role': body['role']}

            self.policy[bucket] = new_policy
            return http_fake.HttpRequestFake(new_policy)


class ObjectsFake(object):
    """A fake object returned by ...objects()."""

    def __init__(self):
        self.bucket_files = {}

    def insert(self, bucket, body, media_body):
        del media_body
        if bucket not in self.bucket_files:
            self.bucket_files[bucket] = []
        self.bucket_files[bucket].append(body['name'])
        return http_fake.HttpRequestFake(body)


class BucketsFake(object):
    """A fake object returned by ...buckets()."""

    def __init__(self):
        self.buckets = ['exist']

    def insert(self, project, body):
        bucket_name = body['name']
        if project != PROJECT_ID:
            return http_fake.HttpRequestFake(
                errors.HttpError(
                    http_fake.HttpResponseFake(403), b'permission denied'))
        elif 'invalid' in bucket_name:
            return http_fake.HttpRequestFake({'invalid': 'response'})
        else:
            self.buckets.append(bucket_name)
            return http_fake.HttpRequestFake(body)


class StorageServiceFake(object):
    def __init__(self):
        self.buckets_fake = BucketsFake()
        self.objects_fake = ObjectsFake()
        self.bucket_access_controls_fake = BucketAccessControlsFake()

    def buckets(self):
        return self.buckets_fake

    def objects(self):
        return self.objects_fake

    def bucketAccessControls(self):
        return self.bucket_access_controls_fake


class StaticContentServeClientTest(absltest.TestCase):
    """Test case for static_content_serve.StaticContentServeClient."""

    def setUp(self):
        self._storage_service_fake = StorageServiceFake()
        self._static_content_serve_client = (
            static_content_serve.StaticContentServeClient(
                self._storage_service_fake))

    def test_create_bucket_success(self):
        self._static_content_serve_client.create_bucket(
            PROJECT_ID, BUCKET_NAME)
        self.assertIn(BUCKET_NAME,
                      self._storage_service_fake.buckets().buckets)

    def test_create_bucket_no_permission(self):
        project_id = 'project_no_permission'
        with self.assertRaises(static_content_serve.StaticContentServeError):
            self._static_content_serve_client.create_bucket(
                project_id, BUCKET_NAME)
        self.assertNotIn(BUCKET_NAME,
                         self._storage_service_fake.buckets().buckets)

    def test_create_bucket_invalid_response(self):
        bucket_name = 'invalid'
        with self.assertRaises(static_content_serve.StaticContentServeError):
            self._static_content_serve_client.create_bucket(
                PROJECT_ID, bucket_name)
        self.assertNotIn(bucket_name,
                         self._storage_service_fake.buckets().buckets)

    def test_make_bucket_public_success(self):
        self._static_content_serve_client.make_bucket_public(BUCKET_NAME)
        self.assertEqual(
            self._storage_service_fake.bucketAccessControls().
            policy[BUCKET_NAME], POLICY)

    def test_make_bucket_public_no_permission(self):
        bucket_name = 'bucket_no_permission'
        with self.assertRaises(static_content_serve.StaticContentServeError):
            self._static_content_serve_client.make_bucket_public(bucket_name)
        self.assertNotIn(
            bucket_name,
            self._storage_service_fake.bucketAccessControls().policy)

    def test_make_bucket_public_invalid_response(self):
        bucket_name = 'invalid'
        with self.assertRaises(static_content_serve.StaticContentServeError):
            self._static_content_serve_client.make_bucket_public(bucket_name)
        self.assertNotIn(
            bucket_name,
            self._storage_service_fake.bucketAccessControls().policy)

    def test_upload_static_content(self):
        # Create a temporary directory looks like the follows:
        # file1
        # dir1
        #   - file2
        with tempfile.TemporaryDirectory() as tmp_dir_root:
            tmp_file_path = os.path.join(tmp_dir_root, 'file1')
            with open(tmp_file_path, 'w') as tmp_file:
                tmp_file.write('file1')
            tmp_dir_path = os.path.join(tmp_dir_root, 'dir1')
            os.mkdir(tmp_dir_path)
            tmp_file_path = os.path.join(tmp_dir_path, 'file2')
            with open(tmp_file_path, 'w') as tmp_file:
                tmp_file.write('file2')

            self._static_content_serve_client.upload_static_content(
                BUCKET_NAME, tmp_dir_root)
            file1_gcs_path = os.path.join(
                self._static_content_serve_client.GCS_ROOT, 'file1')
            file2_gcs_path = os.path.join(
                self._static_content_serve_client.GCS_ROOT, 'dir1', 'file2')
            self.assertIn(
                file1_gcs_path,
                self._storage_service_fake.objects().bucket_files[BUCKET_NAME])
            self.assertIn(
                file2_gcs_path,
                self._storage_service_fake.objects().bucket_files[BUCKET_NAME])
