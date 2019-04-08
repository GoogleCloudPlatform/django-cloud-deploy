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
r"""Create a django app ready to be deployed to gke.

Example: python -m django_cloud_deploy.skeleton --project_name <project_name>
         --app_name <app_name> \
         --destination <destination_path>
"""

import argparse

from django_cloud_deploy.skeleton import source_generator


def add_arguments(parser):
    parser.add_argument('--project_id',
                        default='fake-project-id',
                        help='GCP project id.')
    parser.add_argument('--project_name',
                        default='mysite',
                        help='The name of your Django project.')
    parser.add_argument('--app_name',
                        default='home',
                        help='The name of the app to create')
    parser.add_argument('--project_dir',
                        default='~/django_cloud_project',
                        help='The output folder of your Django project.')
    parser.add_argument(
        '--database_user',
        default='postgres',
        help='Name of the user of the database your Django app want to use.')
    parser.add_argument(
        '--database_password',
        default='fakepassword',
        help=('Password of the user of the database your Django app want to '
              'use.'))
    parser.add_argument(
        '--from-existing',
        default=False,
        help=('Should the generator generate files based on an existing '
              'project'))


def main():
    parser = argparse.ArgumentParser()
    add_arguments(parser)
    args = parser.parse_args()
    generator = source_generator.DjangoSourceFileGenerator()
    generator.generate_new(project_id=args.project_id,
                           project_name=args.project_name,
                           app_name=args.app_name,
                           project_dir=args.project_dir,
                           database_user=args.database_user,
                           database_password=args.database_password)


if __name__ == '__main__':
    main()
