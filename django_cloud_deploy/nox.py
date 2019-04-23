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

import nox

PACKAGES = [
    'pytest==3.6.3',
    'pytest-forked==0.2',
    'pytest-timeout==1.3.2',
    'oauth2client==4.1.2',
    'absl-py==0.3.0',
    'django==2.1.5',
    'backoff==1.8.0',
    'jinja2==2.10',
    'google-cloud-resource-manager==0.28.1',
    'responses==0.9.0',
    'docker==3.4.1',
    'kubernetes==6.0.0',
    'google-cloud-container==0.1.1',
    'grpcio==1.14.1',
    'google-cloud-storage==1.10.0',
    'pexpect==4.6.0',
    'psycopg2-binary==2.7.5',
    'google-api-python-client==1.7.4',
    'google-auth-httplib2==0.0.3',
    'selenium==3.141.0',
    'google-cloud-logging==1.8.0',
    'progressbar2>=3.38.0',
    'portpicker==1.2.0',
    'django-storages==1.7.1',
    'urllib3==1.24.2',
]


# Kokoro Ubuntu images only have python3.4 and python3.5
@nox.session
@nox.parametrize('python_version', ['3.5'])
def unit_test(session, python_version):
    """Run the unit test suite."""

    # Run unit tests against all supported versions of Python.
    session.interpreter = 'python{}'.format(python_version)
    session.install(*PACKAGES)
    session.run('py.test', 'tests/unit', '--timeout=120')


@nox.session
def lint(session):
    """Run linters."""
    session.interpreter = 'python3.5'
    session.install('yapf')
    session.run('yapf', '--diff', '-r', '.')


@nox.session
def type_check(session):
    """Run type checking using pytype."""
    session.interpreter = 'python3.5'
    session.install('..', 'pytype')
    session.run(
        'pytype',
        '--python-version=3.5',
        '--exclude',
        'tests',
        'nox.py',
        '--disable=pyi-error',
        '../django_cloud_deploy',
        # TODO: When pytype passes cleanly, remove allowing
        # all success codes.
        success_codes=range(256))


@nox.session
@nox.parametrize('python_version', ['3.5'])
def integration_test(session, python_version):
    """Run the integration test suite."""

    session.interpreter = 'python{}'.format(python_version)
    session.install(*PACKAGES)
    session.run('py.test', 'tests/integration', '--forked', '--timeout=1800')


@nox.session
@nox.parametrize('python_version', ['3.5'])
def e2e_test_gke(session, python_version):
    """Run the e2e test suite."""

    session.interpreter = 'python{}'.format(python_version)
    session.install(*PACKAGES)
    session.run('py.test', 'tests/e2e/gke_deploy_test.py', '--timeout=1800')


@nox.session
@nox.parametrize('python_version', ['3.5'])
def e2e_test_gae(session, python_version):
    """Run the e2e test suite."""

    session.interpreter = 'python{}'.format(python_version)
    session.install(*PACKAGES)
    session.run('py.test', 'tests/e2e/gae_deploy_test.py', '--timeout=1800')


@nox.session
@nox.parametrize('python_version', ['3.5'])
def e2e_test_gae_cloudify(session, python_version):
    """Run the e2e test suite."""

    session.interpreter = 'python{}'.format(python_version)
    session.install(*PACKAGES)
    session.run('py.test', 'tests/e2e/gae_cloudify_test.py', '--timeout=1800')


@nox.session
@nox.parametrize('python_version', ['3.5'])
def e2e_test_gke_cloudify(session, python_version):
    """Run the e2e test suite."""

    session.interpreter = 'python{}'.format(python_version)
    session.install(*PACKAGES)
    session.run('py.test', 'tests/e2e/gke_cloudify_test.py', '--timeout=1800')


@nox.session
def resource_cleanup(session):
    """Cleanup GCP resources used by tests."""
    session.interpreter = 'python3.5'
    session.install(*PACKAGES)
    session.run('py.test', 'tests/cleanup/resource_cleanup.py')
