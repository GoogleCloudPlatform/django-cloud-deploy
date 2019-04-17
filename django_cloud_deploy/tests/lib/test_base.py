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
import shutil
import subprocess
import tempfile
from typing import Any, List, Dict, Optional
import yaml

from absl.testing import absltest
from google.oauth2 import service_account

import django_cloud_deploy.tests
from django_cloud_deploy.tests.lib import utils
from django_cloud_deploy.skeleton import source_generator
import googleapiclient
from googleapiclient import discovery
from googleapiclient import errors


def _load_test_config():
    """Loads information of the pre-configured gcp project."""

    dirname, _ = os.path.split(
        os.path.abspath(django_cloud_deploy.tests.__file__))
    config_path = os.path.join(dirname, 'integration', 'data',
                               'integration_test_config.yaml')
    with open(config_path) as config_file:
        config_file_content = config_file.read()
    return yaml.load(config_file_content, Loader=yaml.FullLoader)


_TEST_CONFIG = _load_test_config()


class BaseTest(absltest.TestCase):
    """Base class for cloud django integration tests."""

    def setUp(self):
        self.service_account_key_path = os.environ.get(
            'GOOGLE_APPLICATION_CREDENTIALS')

        # The scopes are needed to generate tokens to access clusters on GKE.
        self.credentials = (
            service_account.Credentials.from_service_account_file(
                self.service_account_key_path,
                scopes=['https://www.googleapis.com/auth/cloud-platform']))

    @property
    def zone(self):
        return _TEST_CONFIG['zone']

    @property
    def project_id(self):
        return _TEST_CONFIG['project_id']

    @property
    def project_name(self):
        return _TEST_CONFIG['project_name']


class DjangoFileGeneratorTest(BaseTest):
    """Base class for test cases which need Django project files."""

    @property
    def database_user(self):
        return _TEST_CONFIG['database_user']

    @property
    def database_password(self):
        return _TEST_CONFIG['database_password']

    def setUp(self):
        super().setUp()
        self.project_dir = tempfile.mkdtemp()
        image_name = utils.get_resource_name(resource_type='image')
        self.image_tag = '/'.join(['gcr.io', self.project_id, image_name])
        self.instance_name = utils.get_resource_name(
            resource_type='sql-instance')
        self.database_name = utils.get_resource_name(resource_type='db')
        app_name = 'fake_app'
        generator = source_generator.DjangoSourceFileGenerator()
        generator.generate_new(project_id=self.project_id,
                               project_name=self.project_name,
                               app_name=app_name,
                               project_dir=self.project_dir,
                               database_user=self.database_user,
                               database_password=self.database_password,
                               instance_name=self.instance_name,
                               database_name=self.database_name,
                               image_tag=self.image_tag)

    def tearDown(self):
        shutil.rmtree(self.project_dir)


class ResourceList(BaseTest):
    """Class for listing GCP resources.

    This class is needed by resource cleanup and workflow test.
    """

    def list_service_accounts(self, service=None):
        service = service or discovery.build(
            'iam', 'v1', credentials=self.credentials, cache_discovery=False)
        resource_name = '/'.join(['projects', self.project_id])
        request = service.projects().serviceAccounts().list(name=resource_name)
        accounts = []
        while request:
            response = request.execute()
            # Sometimes the response does not contain any accounts object, but
            # only contains the nextPageToken. At this time, there are still
            # more accounts in the remaining pages.
            accounts += [
                account['email'] for account in response.get('accounts', [])
            ]
            request = service.projects().serviceAccounts().list_next(
                previous_request=request, previous_response=response)
        return accounts

    def list_clusters(self, service=None):
        service = service or discovery.build('container',
                                             'v1',
                                             credentials=self.credentials,
                                             cache_discovery=False)
        request = service.projects().zones().clusters().list(
            projectId=self.project_id, zone=self.zone)
        response = request.execute()
        return [
            cluster.get('name', '') for cluster in response.get('clusters', [])
        ]

    def list_buckets(self, service=None):
        service = service or discovery.build('storage',
                                             'v1',
                                             credentials=self.credentials,
                                             cache_discovery=False)
        request = service.buckets().list(project=self.project_id)
        response = request.execute()
        return [bucket.get('name', '') for bucket in response.get('items', [])]

    def list_enabled_services(self, service_usage_service=None):
        service_usage_service = service_usage_service or discovery.build(
            'serviceusage',
            'v1',
            credentials=self.credentials,
            cache_discovery=False)
        parent = '/'.join(['projects', self.project_id])
        request = service_usage_service.services().list(parent=parent,
                                                        filter='state:ENABLED')
        response = request.execute()
        return [
            service['config']['name']
            for service in response.get('services', [])
        ]

    def list_instances(self, service=None):
        service = service or discovery.build('sqladmin',
                                             'v1beta4',
                                             cache_discovery=False,
                                             credentials=self.credentials)
        request = service.instances().list(project=self.project_id)
        response = request.execute()
        instances = [item['name'] for item in response.get('items', [])]
        return instances

    def list_databases(self, instance_name, service=None):
        service = service or discovery.build('sqladmin',
                                             'v1beta4',
                                             cache_discovery=False,
                                             credentials=self.credentials)
        request = service.databases().list(project=self.project_id,
                                           instance=instance_name)
        response = request.execute()
        databases = [item['name'] for item in response.get('items', [])]
        return databases


class ResourceCleanUp(BaseTest):
    """Class for test cases which need resource cleaning up."""

    def _delete_cluster(
            self,
            cluster_name: str,
            service: Optional[googleapiclient.discovery.Resource] = None):
        container_service = service or discovery.build(
            'container',
            'v1',
            credentials=self.credentials,
            cache_discovery=False)
        request = container_service.projects().zones().clusters().delete(
            projectId=self.project_id, zone=self.zone, clusterId=cluster_name)
        try:
            request.execute()
        except errors.HttpError:
            # These functions are only used in tests and resource cleanings.
            # These are not parts of workflows.
            # In E2E tests, sometimes a the program fail to create an object,
            # trying to delete it will cause errors to get thrown here. Error
            # messages here is misleading and hides the real cause of test
            # failures.
            pass

    @contextlib.contextmanager
    def clean_up_appengine_service(self, service_id: str):
        """A context manager to delete the given app engine service at the end.

        Args:
            service_id: Id of the app engine service to delete.

        Yields:
            None
        """
        try:
            yield
        finally:
            appengine_service = discovery.build('appengine',
                                                'v1',
                                                credentials=self.credentials,
                                                cache_discovery=False)
            request = appengine_service.apps().services().delete(
                appsId=self.project_id, servicesId=service_id)
            try:
                request.execute(num_retries=5)
            except errors.HttpError:
                # These functions are only used in tests and resource cleanings.
                # These are not parts of workflows.
                # In E2E tests, sometimes a the program fail to create an
                # object, trying to delete it will cause errors to get thrown
                # here. Error messages here is misleading and hides the real
                # cause of test failures.
                pass

    def _delete_objects(self, bucket_name: str,
                        storage_service: googleapiclient.discovery.Resource):
        """Delete all objects in the given bucket.

        Needed by clean_up_bucket.

        Args:
            bucket_name: Name of the cluster to delete.
            storage_service: Google client to make api calls.
        """
        request = storage_service.objects().list(bucket=bucket_name)
        response = request.execute(num_retries=5)
        if 'items' in response:  # This bucket might be empty
            object_names = [item['name'] for item in response['items']]
            for object_name in object_names:
                request = storage_service.objects().delete(bucket=bucket_name,
                                                           object=object_name)
                try:
                    request.execute(num_retries=5)
                except errors.HttpError:
                    # These functions are only used in tests and resource
                    # cleanings. These are not parts of workflows.
                    # In E2E tests, sometimes a the program fail to create an
                    # object, trying to delete it will cause errors to get
                    # thrown here. Error messages here is misleading and hides
                    # the real cause of test failures.
                    pass

    def _delete_bucket(
            self,
            bucket_name: str,
            service: Optional[googleapiclient.discovery.Resource] = None):
        storage_service = service or discovery.build(
            'storage',
            'v1',
            credentials=self.credentials,
            cache_discovery=False)
        self._delete_objects(bucket_name, storage_service)
        request = storage_service.buckets().delete(bucket=bucket_name)
        try:
            request.execute(num_retries=5)
        except errors.HttpError:
            # These functions are only used in tests and resource cleanings.
            # These are not parts of workflows.
            # In E2E tests, sometimes a the program fail to create an
            # object, trying to delete it will cause errors to get thrown
            # here. Error messages here is misleading and hides the real
            # cause of test failures.
            pass

    def _delete_service_account(
            self,
            service_account_email: str,
            service: Optional[googleapiclient.discovery.Resource] = None):
        iam_service = service or discovery.build(
            'iam', 'v1', credentials=self.credentials, cache_discovery=False)
        resource_name = 'projects/{}/serviceAccounts/{}'.format(
            self.project_id, service_account_email)
        request = iam_service.projects().serviceAccounts().delete(
            name=resource_name)
        try:
            request.execute(num_retries=5)
        except errors.HttpError:
            # These functions are only used in tests and resource cleanings.
            # These are not parts of workflows.
            # In E2E tests, sometimes a the program fail to create an
            # object, trying to delete it will cause errors to get thrown
            # here. Error messages here is misleading and hides the real
            # cause of test failures.
            pass

    def _reset_iam_policy(
            self,
            member: str,
            roles: List[str],
            service: Optional[googleapiclient.discovery.Resource] = None):
        cloudresourcemanager_service = service or discovery.build(
            'cloudresourcemanager',
            'v1',
            credentials=self.credentials,
            cache_discovery=False)
        request = cloudresourcemanager_service.projects().getIamPolicy(
            resource=self.project_id)
        policy = request.execute(num_retries=5)
        for role in roles:
            # Remove the given members for a role
            for binding in policy['bindings']:
                if binding['role'] == role and member in binding['members']:
                    binding['members'].remove(member)
                    break

        # Remove any empty bindings.
        policy['bindings'] = [b for b in policy['bindings'] if b['members']]
        body = {'policy': policy}
        request = cloudresourcemanager_service.projects().setIamPolicy(
            resource=self.project_id, body=body)
        try:
            request.execute(num_retries=5)
        except errors.HttpError:
            # These functions are only used in tests and resource cleanings.
            # These are not parts of workflows.
            # In E2E tests, sometimes a the program fail to create an
            # object, trying to delete it will cause errors to get thrown
            # here. Error messages here is misleading and hides the real
            # cause of test failures.
            pass

    def _clean_up_sql_instance(
            self,
            instance_name: str,
            service: Optional[googleapiclient.discovery.Resource] = None):
        sqladmin_service = service or discovery.build(
            'sqladmin',
            'v1beta4',
            credentials=self.credentials,
            cache_discovery=False)
        request = sqladmin_service.instances().delete(instance=instance_name,
                                                      project=self.project_id)
        try:
            request.execute(num_retries=5)
        except errors.HttpError:
            # These functions are only used in tests and resource cleanings.
            # These are not parts of workflows.
            # In E2E tests, sometimes a the program fail to create an
            # object, trying to delete it will cause errors to get thrown
            # here. Error messages here is misleading and hides the real
            # cause of test failures.
            pass

    def _clean_up_database(
            self,
            instance_name: str,
            database_name: str,
            service: Optional[googleapiclient.discovery.Resource] = None):
        sqladmin_service = service or discovery.build(
            'sqladmin',
            'v1beta4',
            credentials=self.credentials,
            cache_discovery=False)
        request = sqladmin_service.databases().delete(database=database_name,
                                                      instance=instance_name,
                                                      project=self.project_id)
        try:
            request.execute(num_retries=5)
        except errors.HttpError:
            # These functions are only used in tests and resource cleanings.
            # These are not parts of workflows.
            # In E2E tests, sometimes a the program fail to create an
            # object, trying to delete it will cause errors to get thrown
            # here. Error messages here is misleading and hides the real
            # cause of test failures.
            pass

    @contextlib.contextmanager
    def clean_up_cluster(self, cluster_name: str):
        """A context manager to delete the given cluster at the end.

        Args:
            cluster_name: Name of the cluster to delete.

        Yields:
            None
        """
        try:
            yield
        finally:
            self._delete_cluster(cluster_name)

    @contextlib.contextmanager
    def clean_up_bucket(self, bucket_name: str):
        """A context manager to delete the given GCS bucket.

        Args:
            bucket_name: Name of the GCS bucket to delete.

        Yields:
            None
        """
        try:
            yield
        finally:
            self._delete_bucket(bucket_name)

    @contextlib.contextmanager
    def clean_up_docker_image(self, image_name: str):
        """A context manager to delete the given docker image.

        Args:
            image_name: Name of the docker image to delete.

        Yields:
            None
        """
        try:
            yield
        finally:
            # TODO: Rewrite this subprocess call with library call.
            digests = subprocess.check_output(
                [
                    'gcloud', 'container', 'images', 'list-tags',
                    '--format=value(digest)', image_name
                ],
                universal_newlines=True).rstrip().split('\n')
            for digest in digests:
                full_image_name = '{}@sha256:{}'.format(image_name, digest)
                subprocess.check_call([
                    'gcloud', '-q', 'container', 'images', 'delete',
                    '--force-delete-tags', full_image_name
                ])

    @contextlib.contextmanager
    def disable_services(self, services: List[Dict[str, Any]]):
        """A context manager to disable the given services.

        Args:
            services: List of the services to disable.

        Yields:
            None
        """
        try:
            yield
        finally:
            service_usage_service = discovery.build(
                'serviceusage',
                'v1',
                credentials=self.credentials,
                cache_discovery=False)
            for service in services:
                service_name = '/'.join(
                    ['projects', self.project_id, 'services', service['name']])
                request = service_usage_service.services().disable(
                    name=service_name, body={'disableDependentServices': False})
                try:
                    request.execute(num_retries=5)
                except errors.HttpError:
                    # These functions are only used in tests and resource
                    # cleanings. These are not parts of workflows.
                    # In E2E tests, sometimes a the program fail to create an
                    # object, trying to delete it will cause errors to get
                    # thrown here. Error messages here is misleading and hides
                    # the real cause of test failures.
                    pass

    @contextlib.contextmanager
    def delete_service_account(self, service_account_email: str):
        """A context manager to delete the given service account.

        Args:
            service_account_email: Email of the service account to delete.

        Yields:
            None
        """
        try:
            yield
        finally:
            self._delete_service_account(service_account_email)

    @contextlib.contextmanager
    def reset_iam_policy(self, member: str, roles: List[str]):
        """Remove bindings as specified by the args.

        If we only delete the service account, the role bindings for that
        service account still exist. So we need to also reset the iam policy.

        Args:
            member: The member to remove from the IAM policy. If should
                have the following format:
                "serviceAccount:{sa_id}@{project_id}.iam.gserviceaccount.com"
            roles: The roles the member should be removed from. Valid roles
                can be found on
                https://cloud.google.com/iam/docs/understanding-roles

        Yields:
            Nothing
        """

        try:
            yield
        finally:
            self._reset_iam_policy(member, roles)

    @contextlib.contextmanager
    def clean_up_sql_instance(self, instance_name: str):
        """A context manager to delete the given Cloud SQL instance.

        Args:
            instance_name: Name of the Cloud SQL instance to delete.

        Yields:
            None
        """
        try:
            yield
        finally:
            self._clean_up_sql_instance(instance_name)

    @contextlib.contextmanager
    def clean_up_database(self, instance_name: str, database_name: str):
        """A context manager to delete the given Cloud SQL database.

        Args:
            instance_name: Name of the Cloud SQL instance the database belongs
                to.
            database_name: Name of the database to delete.

        Yields:
            None
        """
        try:
            yield
        finally:
            self._clean_up_database(instance_name, database_name)

    @contextlib.contextmanager
    def clean_up_cloudbuild_trigger(self, repo_name: str):
        try:
            yield
        finally:
            service = discovery.build('cloudbuild',
                                      'v1',
                                      credentials=self.credentials,
                                      cache_discovery=False)
            request = service.projects().triggers().list(
                projectId=self.project_id)
            triggers = []
            while request:
                response = request.execute()
                triggers += response.get('triggers', [])
                request = service.projects().triggers().list_next(
                    previous_request=request, previous_response=response)
            victim_ids = [
                trigger.get('id')
                for trigger in triggers
                if trigger.get('triggerTemplate').get('repoName') == repo_name
            ]
            for victim_id in victim_ids:
                request = service.projects().triggers().delete(
                    projectId=self.project_id, triggerId=victim_id)
                try:
                    request.execute(num_retries=5)
                except errors.HttpError:
                    pass

    @contextlib.contextmanager
    def clean_up_repo(self, repo_name: str):
        """A context manager to delete the given Cloud Source Repository.

        Args:
            repo_name: Name of the cloud source repository.

        Yields:
            None
        """
        try:
            yield
        finally:
            service = discovery.build('sourcerepo',
                                      'v1',
                                      credentials=self.credentials,
                                      cache_discovery=False)
            resource_name = 'projects/{}/repos/{}'.format(
                self.project_id, repo_name)
            request = service.projects().repos().delete(name=resource_name)
            try:
                request.execute(num_retries=5)
            except errors.HttpError:
                pass
