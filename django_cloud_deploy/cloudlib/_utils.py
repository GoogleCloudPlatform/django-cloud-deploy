# Copyright 2018 Google LLC
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
"""Helper file for common functionality within cloublib."""

def set_user_agent(http, user_agent):
    """Set the user-agent on every request.

    Args:
       http - An instance of google_auth_httplib2.AuthorizedHttp.
       user_agent: string, the value for the user-agent header.

    Returns:
       A modified instance of http that was passed in.

    Example:

      h = httplib2.Http()
      h = set_user_agent(h, "my-app-name/6.0")

    Most of the time the user-agent will be set doing auth, this is for the rare
    cases where you are accessing an unauthenticated endpoint.
    """
    request_orig = http.request
    default_max_redirects = 5

    # The closure that will replace 'httplib2.Http.request'.
    def new_request(uri, method='GET', body=None, headers=None,
                    redirections=default_max_redirects,
                    connection_type=None):
        """Modify the request headers to add the user-agent."""

        if headers is None:
            headers = {}
        if 'user-agent' in headers:
            headers['user-agent'] = user_agent + ' ' + headers['user-agent']
        else:
            headers['user-agent'] = user_agent
        resp, content = request_orig(uri, method, body, headers,
                                     redirections=redirections,
                                     connection_type=connection_type)
        return resp, content

    http.request = new_request
    return http