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
"""A module help parse requirements.txt."""

import os
import re
from typing import Set


def parse_line(line: str) -> str:
    """Parse a single line in requirements.txt.

    Note that this function only returns the package that is required, without
    version restrictions
    e.g. "google-cloud-bigquery>1.2.3" => "google-cloud-bigquery".

    Args:
        line: A line in requirements.txt.

    Returns:
        The package requirement contained on the line
        e.g. "google-cloud-bigquery".
    """

    # See
    # https://pip.pypa.io/en/stable/reference/pip_install/#requirement-specifiers
    return re.split(r'[;\[~>=<]', line)[0].strip().lower()


def parse(path: str) -> Set[str]:
    """Parses requirements given the absolute path of a requirements.txt.

    Note that this function only returns the package that is required, without
    version restrictions
    e.g. "google-cloud-bigquery>1.2.3" => "google-cloud-bigquery".

    Args:
        path: Absolute path of a requirements.txt.

    Returns:
        The set of packages contained in the given "requirements.txt".
    """

    results = set()
    if not os.path.exists(path):
        return results

    dir_path = os.path.dirname(path)
    with open(path) as requirements_file:
        lines = requirements_file.read().splitlines()
        for line in lines:
            line = line.strip()
            # This does not handle the full grammar, for example, line
            # continuation, package from a url, or package from a local path
            # TODO: Support more kinds of packages
            if not line or line.startswith('#'):
                continue
            elif line.startswith('-r'):
                # This will install a list of requirements specified in a file
                sub_requirements_path = line.split(' ')[-1]
                results = results.union(
                    parse(os.path.join(dir_path, sub_requirements_path)))
            else:
                results.add(parse_line(line))
    return results
