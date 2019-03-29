# Copyright 2019 Google LLC
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
"""Functions for asking users to take a survey at the end of deployment."""

from django_cloud_deploy.cli import io
from django_cloud_deploy.cli import prompt
from django_cloud_deploy.utils import webbrowser

_SURVEY_LINK = 'https://google.qualtrics.com/jfe/form/SV_3wwUubKBJnC7Fxr'


def prompt_for_survey(console: io.IO):
    """Ask users to take a survey.

    If the user would like to take the survey, then the method will open
    their web browser and direct them to an existing Qualtrics survey.

    Args:
        console: Object to use for user I/O.
    """
    msg = ('Would you like to take a survey to provide your feedback for '
           'the deployment process? [y/N]')

    do_survey = prompt.binary_prompt(msg, console, default=False)
    if do_survey:
        webbrowser.open_url(_SURVEY_LINK)
