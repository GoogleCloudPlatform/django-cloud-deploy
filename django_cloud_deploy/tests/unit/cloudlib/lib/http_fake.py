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

    def execute(self):
        if isinstance(self.response, errors.HttpError):
            raise self.response
        return self.response


class HttpResponseFake(object):
    """A fake googleapiclient.http.HttpResponse."""

    def __init__(self, status):
        self.status = status
        self.reason = 'unknown'
