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

import random
import re

from django_cloud_deploy.cloudlib import project
from django_cloud_deploy.utils import base_client
from django_cloud_deploy.utils import workflow_io

CREATE_GCP_PROJECT = '''
  i. If you have set $GOOGLE_APPLICATION_CREDENTIALS environment variable,
  please make sure your service account has access to manage your data across
  Google Cloud Platform services. Otherwise unset that variable and run
  “gcloud auth application-default login”.
  ii. If you receive permission errors, please run
  "rm ~/.config/gcloud/application_default_credentials.json"
  iii. If you still have permission errors, please run
  “gcloud auth application-default login”
'''

PROJECT_NAME_PROMPT_TEMPLATE = '''
Enter a Project Name. Project Names must be 1-24 characters (letters, digits,
or whitespaces). Use [{}] by pressing enter:
'''


class GoogleClient(base_client.BaseClient):
    """ Encapsulates the logic to set up a new GKE project on GCP.

  This class has the logic required for the workflow steps a user needs
  to go through to set up a new project on GCP. This is the "first half" for a
  user to get their Django GKE project deployed. It gets instantiated with an
  IO Class that allows better logging with user interactions. Uses google
  application default credentials for authentication, which are generated via
  Gcloud.

    Typical usage example:
        client = GoogleClient(WorkflowIO.Console())
        client.create_project_workflow()


  Args:
    io: IO class that manages our user interactions
    creds: (Optional) The OAuth2 Credentials to use for this
                      client. If not passed (and if no ``_http`` object is
                      passed), falls back to the default inferred from the
                      environment.
  """

    def __init__(self,
                 io: workflow_io.IO,
                 project_client: project.ProjectClient,
                 debug=False):
        """
    Will use the default application credentials. If they
    have not been generated, then they will be generated via google-auth.
    The resource_manager package will look for them in their default location.

    Args:
      io: Input/Output Handling Class.
      creds: Optionally pass in credentials instead of using the default
      application credentials. Also used to pass mocked creds.
      debug: Whether this client uses debug mode.
    """
        super().__init__(debug)
        self._project_client = project_client
        self.workflow = workflow_io.Workflow(io)

    def create_project_workflow(self, project_id=None) -> str:
        """Starts the GCP Project creation workflow.

    Makes API calls to GCP to create a project.

    See google-cloud-resource-manager:
    https://googlecloudplatform.github.io/google-cloud-python/latest/resource-manager/api.html#

    Args:
      project_id: str or None. Test only, do not use. If this parameter is
                  provided, we will use the provided project id instead of
                  generating a random one based on the project name.
    Returns:
      A generated project id based on the project name that the user gave.

    Raises:
      RuntimeError: If project does not exist after 9 seconds
       it throws an error
    """
        self.workflow.tell(CREATE_GCP_PROJECT)
        project_name = self._prompt_project_input()
        self.workflow.tell(
            'Please wait while project %s is being created' % project_name)
        if project_id:
            self._project_client.set_existing_project(project_id)
        else:
            project_id = self._generate_project_id(project_name)
            self._project_client.create_and_set_project(project_id,
                                                        project_name)
            self.workflow.tell('Project %s created. It\'s project id is %s' %
                               (project_name, project_id))
        return project_id

    @staticmethod
    def _generate_project_id(project_name: str) -> str:
        """Generate a project id based on given project name.

    The generated project id will replace whitespace and underscores with
    hyphens.

    Args:
      project_name: Input string which should represent a project name.
    Returns:
      Generated project id.
    """
        random_suffix = str(random.randint(100000, 999999))
        project_id = project_name.lower().replace(' ', '-').replace('_', '-')
        if project_id[-1] != '-':
            project_id += '-'
        return project_id + random_suffix

    @staticmethod
    def _is_valid_project_name(project_name: str) -> bool:
        """Checks whether the input is a valid project id.

    A valid project id should be 6-30 characters long and only contains lower
    case ASCII, digits, or hyphens.

    Args:
      project_name: Input string which should represent a project id.
    Returns:
      Whether the input string is a valid project id.
    """
        return (len(project_name) and len(project_name) <= 24 and
                re.fullmatch(r'^[\w\s]+$', project_name) is not None)

    # noinspection PyMethodMayBeStatic
    def _prompt_project_input(self) -> str:
        default_value = 'Djangogke Project'
        project_name_prompt = PROJECT_NAME_PROMPT_TEMPLATE.format(default_value)
        error_msg = (
            'A valid project name should be 1-24 characters long and only '
            'contains letters, digits, underscore or whitespaces. Please use '
            'another name and try again')
        return self.workflow.ask(project_name_prompt, default_value,
                                 self._is_valid_project_name, error_msg)
