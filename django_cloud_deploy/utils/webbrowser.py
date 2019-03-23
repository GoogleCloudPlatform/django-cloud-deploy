# Copyright 2019 Google LLC
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
"""Webbrowser utility functions."""

import os
import webbrowser


def open_url(url: str):
    """Filter ugly terminal output when using webbrowser.

    When using webbrowser.open the follow error is shown:
    [20451:20471:0313/132752.481635:ERROR:browser_process_sub_thread.cc(209)]
    Waited 3 ms for network service.
    In attempts to improve UX when using the CLI, we are surpressing that
    error with the following utility. For more information refer to:
    http://man7.org/linux/man-pages/man2/dup.2.html
    """

    # Save previous standard file descriptors
    prev_stderr_fd = os.dup(2)
    prev_stdout_fd = os.dup(1)
    with open(os.devnull, 'wb') as f:
        # redirect stderr and stdout to os.devnull
        os.dup2(f.fileno(), 2)
        os.dup2(f.fileno(), 1)
        try:
            webbrowser.open(url)
        except webbrowser.Error:
            # We are not able to do anything if any internal errors happen
            # with webbrowser.open()
            pass
        finally:
            # restore stdout and stderr
            os.dup2(prev_stdout_fd, 1)
            os.dup2(prev_stderr_fd, 2)
