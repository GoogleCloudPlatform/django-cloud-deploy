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

import json
import os
import shutil
import stat
import subprocess
import sys
import urllib.request
import webbrowser

from typing import List, Callable

from django_cloud_deploy.utils import workflow_io


class MissingDependencyError(Exception):
    pass


class Requirement(object):

    def __init__(self,
                 requirement: str,
                 requirement_msg: str,
                 raise_error: bool,
                 download_link: str = None):
        self.requirement = requirement
        self.requirement_msg = requirement_msg
        self.raise_error = raise_error
        self.download_link = download_link


class RequirementsClient(object):

    def __init__(self, requirements_list: List[Requirement],
                 io: workflow_io.IO):
        self.requirement_list = requirements_list
        self.workflow = workflow_io.Workflow(io)

    def missing_requirements(self):
        check_function = shutil.which
        return [
            r.requirement
            for r in self.requirement_list
            if not self.has_requirement(r, check_function)
        ]

    @staticmethod
    def requirement_on_path(executable_name: str):
        return shutil.which(executable_name)

    @staticmethod
    def has_requirement(req: Requirement,
                        check_function: Callable,
                        install_function: Callable = None) -> bool:
        """ Checks if requirement is met.

    Args:
      req: The requirement needed.
      check_function: Function that will check if requirement is installed
      install_function: Function that will install the requirement.

    Returns:
      Default to bool, but if fail_function was passed, it returns the return
      value of the fail_function.

    """
        if check_function(req.requirement):
            return True

        if install_function is not None:
            install_function(req.download_link)

        if req.raise_error:
            raise MissingDependencyError(
                '%s needs to be installed' % req.requirement_msg)

        return False

    @staticmethod
    def requirement_missing(req: Requirement):
        print('Please download {} '
              'from {}'.format(req.requirement_msg, req.download_link))
        webbrowser.open(req.download_link)

    @staticmethod
    def is_docker_usable() -> bool:
        """
    Checks if the user can use docker. TODO: check if externally applicable
    """
        try:
            command = 'docker image ls'.split(' ')
            subprocess.check_call(
                command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except:  # noqa: E722
            print('Use the following command: sudo usermod -a -G docker $USER\n'
                  'Then log out/log back in')
            return False

    def get_cloud_sql_proxy(self) -> str:
        req = Requirement('cloud_sql_proxy', 'Cloud Sql Proxy', False)

        # Check if user has it on the path
        if self.has_requirement(req, shutil.which):
            return req.requirement

        can_download = self.prompt_download_requirement([req])
        if can_download:
            return self.download_cloud_sql_proxy()
        else:
            raise MissingDependencyError('Cloud Sql Proxy is required')

    @staticmethod
    def load_requirements():
        DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
        fp = os.path.join(DATA_DIR, 'requirements.json')
        with open(fp) as f:
            requirements = json.load(f)
            requirements = [Requirement(**r) for r in requirements]
        return requirements

    def prompt_download_requirement(self, reqs: List[Requirement]) -> bool:
        self.workflow.tell('The following are required:')
        for req in reqs:
            self.workflow.tell('  * {}'.format(req.requirement))
        answer = self.workflow.ask(
            'y/n to download requirements [press enter for yes]:', 'y')
        return answer.lower().startswith('y')

    def download_cloud_sql_proxy(self):
        import certifi

        # We will install the proxy where gcloud is
        gcloud_dir = os.path.dirname(shutil.which('gcloud'))
        if sys.platform.startswith('linux'):
            url = 'https://dl.google.com/cloudsql/cloud_sql_proxy.linux.amd64'
        elif sys.platform.startswith('darwin'):
            url = 'https://dl.google.com/cloudsql/cloud_sql_proxy.darwin.amd64'
        else:
            msg = '{} is not supported, only linux/mac.'.format(sys.platform)
            raise NotImplementedError(msg)

        self.workflow.tell('Downloading Cloud Sql Proxy')

        file_name = 'cloud_sql_proxy'
        executable_name = os.path.join(gcloud_dir, file_name)
        with open(executable_name, 'wb') as file:
            with urllib.request.urlopen(url, cafile=certifi.where()) as data:
                file.write(data.read())

        st = os.stat(executable_name)
        os.chmod(executable_name, st.st_mode | stat.S_IRWXU)

        return file_name
