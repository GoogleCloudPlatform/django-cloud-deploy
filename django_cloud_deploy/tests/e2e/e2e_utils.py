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
"""Utilities for E2E tests."""

import subprocess

import backoff
from django_cloud_deploy.cli import io
import requests


@backoff.on_exception(backoff.expo,
                      requests.exceptions.ConnectionError,
                      max_tries=5)
def get_with_retry(url: str) -> requests.models.Response:
    return requests.get(url)


@backoff.on_predicate(backoff.expo, logger=None, max_tries=5)
def wait_for_appengine_update_ready(project_id: str, service_name: str) -> bool:
    """Returns when 100% traffic is put to the latest app.

    Otherwise retries for at most 5 times and returns.

    Args:
        project_id: Id of the GCP project.
        service_name: Name of the App Engine service.
    """
    command = [
        'gcloud', '--project=' + project_id, 'app', 'versions', 'list',
        '--service=' + service_name, '--hide-no-traffic',
        '--format=csv[no-heading](TRAFFIC_SPLIT)'
    ]
    result = subprocess.check_output(
        command, universal_newlines=True).rstrip().splitlines()
    if len(result) <= 1:
        return False
    traffic = float(result[-1])
    return traffic > 0


def create_new_command_io(project_id: str, project_dir: str,
                          django_project_name: str) -> io.TestIO:
    """Create a io.TestIO object with information required by new command.

    Args:
        project_id: GCP project id.
        project_dir: Absolute directory of the Django project you want to
            deploy.
        django_project_name: Name of the Django project.

    Returns:
        An io.TestIO object with information required by new command.
    """
    test_io = io.TestIO()
    test_io.answers.append(project_id)  # project_id
    test_io.password_answers.append('fake_password')  # database password
    # database password again
    test_io.password_answers.append('fake_password')
    test_io.answers.append(project_dir)  # django_directory_path
    # The Django local directory is created with tempfile.mkdtemp().
    # So when we get this prompt, it exists already. We need to
    # overwrite it.
    test_io.answers.append('Y')
    test_io.answers.append(django_project_name)  # django_project_name
    test_io.answers.append('')  # django_app_name
    # django_superuser_login
    test_io.answers.append('admin')
    # django_superuser_password
    test_io.password_answers.append('fake_password')
    # django_superuser_password again
    test_io.password_answers.append('fake_password')
    test_io.answers.append('')  # django_superuser_email
    test_io.answers.append('N')  # Do not do survey at the end
    return test_io


def create_update_command_io(project_dir: str) -> io.TestIO:
    """Create a io.TestIO object with information required by update command.

    Args:
        project_dir: Absolute directory of the Django project you want to
            deploy.

    Returns:
        An io.TestIO object with information required by update command.
    """
    test_io = io.TestIO()
    test_io.password_answers.append('fake_password')  # database password
    test_io.password_answers.append('fake_password')  # Confirm password
    test_io.answers.append(project_dir)  # django_directory_path
    return test_io


def create_cloudify_command_io(project_id: str, project_dir: str,
                               requirements_path: str,
                               settings_path: str) -> io.TestIO:
    """Create a io.TestIO object with information required by cloudify command.

    Args:
        project_id: GCP project id.
        project_dir: Absolute directory of the Django project you want to
            deploy.
        requirements_path: Absolute path of the requirements.txt of your Django
            project.
        settings_path: Absolute path of the settings file of your Django
            project.

    Returns:
        An io.TestIO object with information required by cloudify command.
    """
    test_io = io.TestIO()
    test_io.answers.append(project_id)  # project_id
    test_io.password_answers.append('fake_password')  # database password
    # database password again
    test_io.password_answers.append('fake_password')
    # django_directory_path_cloudify
    test_io.answers.append(project_dir)
    # django_requirements_path
    test_io.answers.append(requirements_path)
    # django_settings_path
    test_io.answers.append(settings_path)
    # django_superuser_login
    test_io.answers.append('admin')
    # django_superuser_password
    test_io.password_answers.append('fake_password')
    # django_superuser_password again
    test_io.password_answers.append('fake_password')
    test_io.answers.append('')  # django_superuser_email
    test_io.answers.append('N')  # Do not do survey at the end
    return test_io
