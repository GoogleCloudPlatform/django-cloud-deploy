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
"""Module for fake http requests and responses."""

from googleapiclient import errors


class HttpRequestFake(object):
    """A fake googleapiclient.http.HttpRequest."""

    def __init__(self, response):
        self.response = response

    def execute(self, num_retries=0):
        if isinstance(self.response, errors.HttpError):
            raise self.response
        return self.response


class HttpRequestFakeMultiple(object):
    """A fake googleapiclient.http.HttpRequest.

    This class will return multiple kinds of responses.
    """

    def __init__(self, responses):
        self.responses = responses
        self.call_count = 0

    def execute(self, num_retries=0):
        if self.call_count >= len(self.responses):
            return None
        response = self.responses[self.call_count]
        self.call_count += 1
        if isinstance(response, errors.HttpError):
            raise response
        return response


class HttpResponseFake(object):
    """A fake googleapiclient.http.HttpResponse."""

    def __init__(self, status):
        self.status = status
        self.reason = 'unknown'
