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
    'oauth2client==4.1.2',
    'absl-py==0.3.0',
    'django==2.1',
    'backoff==1.6.0',
    'jinja2==2.10',
    'google-cloud-resource-manager==0.28.1',
    'responses==0.9.0',
    'docker==3.4.1',
    'kubernetes==6.0.0',
    'google-cloud-container==0.1.1',
    'grpcio==1.14.1',
    'google-cloud.storage==1.10.0',
    'pexpect==4.6.0',
    'psycopg2-binary==2.7.5',
    'google-api-python-client==1.7.4',
]


# Kokoro Ubuntu images only have python3.4 and python3.5
@nox.session
@nox.parametrize('python_version', ['3.5'])
def unit_test(session, python_version):
    """Run the unit test suite."""

    # Run unit tests against all supported versions of Python.
    session.interpreter = 'python{}'.format(python_version)
    session.install(*PACKAGES)
    session.run('pytest', '--ignore=integration_tests')


@nox.session
def lint(session):
    """Run linters."""
    session.interpreter = 'python3.5'
    session.install('flake8')
    session.run('flake8')


@nox.session
@nox.parametrize('python_version', ['3.5'])
def integration_test(session, python_version):
    """Run the unit test suite."""

    session.interpreter = 'python{}'.format(python_version)
    session.install(*PACKAGES)
    session.run('pytest', 'integration_tests')
