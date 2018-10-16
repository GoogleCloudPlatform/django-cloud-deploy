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
         --app_names <app_name1> <app_name2> \
         --destination <destination_path>
"""

import argparse

from django_cloud_deploy.skeleton import source_generator


def add_arguments(parser):
    parser.add_argument(
        '--project_id', default='fake-project-id', help='GCP project id.')
    parser.add_argument(
        '--project_name',
        default='mysite',
        help='The name of your Django project.')
    parser.add_argument(
        '--app_names',
        nargs='+',
        default=['polls'],
        help='A list of names of apps to create')
    parser.add_argument(
        '--destination',
        default='~/djangogke_project',
        help='The output folder of your Django project.')


def main():
    parser = argparse.ArgumentParser()
    add_arguments(parser)
    args = parser.parse_args()
    generator = source_generator.DjangoSourceFileGenerator()
    generator.generate_all_source_files(
        project_id=args.project_id,
        project_name=args.project_name,
        app_names=args.app_names,
        destination=args.destination)


if __name__ == '__main__':
    main()
