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
"""Integration tests for module django_cloud_deploy.cloudlib."""

from django_cloud_deploy.cloudlib import static_content_serve
from django_cloud_deploy.tests.lib import test_base
from django_cloud_deploy.tests.lib import utils


class StaticContentServeClientIntegrationTest(test_base.DjangoFileGeneratorTest,
                                              test_base.ResourceCleanUpTest):
    """Integration test for django_gke.cloudlib.static_content_serve."""

    def setUp(self):
        super().setUp()
        self._static_content_serve_client = (
            static_content_serve.StaticContentServeClient.from_credentials(
                self.credentials))

    def test_reuse_bucket(self):
        bucket_name = utils.get_resource_name('bucket')
        with self.clean_up_bucket(bucket_name):
            for _ in range(3):
                self._static_content_serve_client.create_bucket(
                    self.project_id, bucket_name)
