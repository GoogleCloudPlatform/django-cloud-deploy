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

import argparse
import sys
import warnings

import django_cloud_deploy.crash_handling
from django_cloud_deploy.cli import cloudify
from django_cloud_deploy.cli import new
from django_cloud_deploy.cli import update


def _update(args):
    """Update the Django project on GKE."""
    try:
        update.main(args)
    except Exception as e:
        django_cloud_deploy.crash_handling.handle_crash(
            e, 'django-cloud-deploy update')


def _new(args):
    """Create a new Django GKE project."""
    try:
        new.main(args)
    except Exception as e:
        django_cloud_deploy.crash_handling.handle_crash(
            e, 'django-cloud-deploy new')


def _cloudify(args):
    """Deploy an existing Django project."""
    try:
        cloudify.main(args)
    except Exception as e:
        django_cloud_deploy.crash_handling.handle_crash(
            e, 'django-cloud-deploy cloudify')


def main():
    warnings.filterwarnings(
        'ignore',
        ('Your application has authenticated using end user credentials from '
         'Google Cloud SDK.'))

    parser = argparse.ArgumentParser(description='')
    subparsers = parser.add_subparsers(title='subcommands')
    new_parser = subparsers.add_parser(
        'new',
        description=('Create a new Django project and deploy it to Google '
                     'Kubernetes Engine.'))
    new_parser.set_defaults(func=_new)
    new.add_arguments(new_parser)
    update_parser = subparsers.add_parser(
        'update',
        description=('Deploys an Django project, previously created with '
                     'django_cloud_deploy, on Google Kubernetes Engine.'))
    update_parser.set_defaults(func=_update)
    update.add_arguments(update_parser)
    cloudify_parser = subparsers.add_parser(
        'cloudify',
        description=('Modifies the settings for an existing Django projects'
                     'and deploys it to the cloud.'))
    cloudify_parser.set_defaults(func=_cloudify)
    cloudify.add_arguments(cloudify_parser)
    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)
    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
