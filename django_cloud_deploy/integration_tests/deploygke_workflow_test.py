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

import contextlib
import os
import subprocess

import requests

from google.cloud import container_v1
from google.cloud import storage

from django_cloud_deploy.deploygke import deploygke
from django_cloud_deploy.integration_tests.lib import test_base
from django_cloud_deploy.integration_tests.lib import utils


class DeploygkeWorkflowIntegrationTest(test_base.DjangoFileGeneratorTest):

    def setUp(self):
        super().setUp()
        self.deploygke_workflow = deploygke.DeploygkeWorkflow(
            self.project_id, self.project_name, self.project_dir, debug=True)

    @contextlib.contextmanager
    def clean_up_cluster(self, cluster_name):
        try:
            yield
        finally:
            client = container_v1.ClusterManagerClient(
                credentials=self.credentials)
            client.delete_cluster(self.project_id, self.zone, cluster_name)

    @contextlib.contextmanager
    def clean_up_gcs_bucket(self, bucket_name):
        try:
            yield
        finally:
            client = storage.Client(
                project=self.project_id, credentials=self.credentials)
            bucket = client.get_bucket(bucket_name)
            bucket.delete(force=True)

    @contextlib.contextmanager
    def clean_up_docker_image(self, image_tag):
        try:
            yield
        finally:
            subprocess.check_call(
                ['gcloud', 'container', 'images', 'delete', image_tag, '-q'])

    def test_deploygke_workflow(self):
        cluster_name = utils.get_resource_name(resource_type='cluster')
        bucket_name = utils.get_resource_name(resource_type='bucket')

        with self.clean_up_cluster(cluster_name), \
                self.clean_up_docker_image(self.image_tag), \
                self.clean_up_gcs_bucket(bucket_name):
            # This is the service account key file used to authenticate gcloud.
            # It has access to manage all resources. Because generation of
            # service account key is not part of this test case, I just reuse
            # this existing service account key file.
            service_account_key_path = os.environ[
                'GOOGLE_APPLICATION_CREDENTIALS']
            os.environ.setdefault('DATABASE_USER', 'fake_db_user')
            os.environ.setdefault('DATABASE_PASSWORD', 'fake_db_password')
            admin_url = self.deploygke_workflow.deploygke(
                service_account_key_path,
                'fake_admin_user',
                cluster_name=cluster_name,
                bucket_name=bucket_name,
                image_tag=self.image_tag,
                open_browser=False)
            response = requests.get(admin_url)
            self.assertIn('Django administration', response.text)

            # Test static contents are uploaded
            client = storage.Client()
            bucket = client.get_bucket(bucket_name)
            file_names = [blob.name for blob in bucket.list_blobs()]
            self.assertIn('static/admin/css/base.css', file_names)
