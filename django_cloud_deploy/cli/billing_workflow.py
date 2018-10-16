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

import webbrowser

from googleapiclient import discovery

from django_cloud_deploy.utils import workflow_io


class BillingWorkflow(object):

    def __init__(self, project_id: str, io: workflow_io.IO, http=None):
        self.project_id = project_id
        self.workflow = workflow_io.Workflow(io)
        self.billing_service = (discovery.build(
            'cloudbilling', 'v1', http=http))

    def billing_workflow(self):
        """ Instructs user to set up billing for given project_id.

    Confirms given project_id has billing. Sends user to the GCP console
    to set it up via their webbrowser.

    """
        self.workflow.tell('Billing is required for project %s '
                           'to deploy to GKE' % self.project_id)

        billing_url = (
            'https://console.cloud.google.com/billing/linkedaccount?project={}')

        webbrowser.open(billing_url.format(self.project_id))
        self.workflow.tell('Please set up billing to continue')
        self.workflow.ask('Press enter once billing has been set up\n')

    # TODO: Remove or replace this functionality
    # def _check_project_has_billing(self):
    #   project_name = 'projects/' + self.project_id
    #   billing_info = (self.billing_service
    #                   .projects()
    #                   .getBillingInfo(name=project_name)
    #                   .execute())
    #   return billing_info.get('billingEnabled', False)
