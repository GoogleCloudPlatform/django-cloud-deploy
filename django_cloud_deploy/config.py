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
"""A module about YAML formated configuration files generation.

The configuration files are expected to capture the state of Django projects.
"""

import os
from typing import Any, Optional
import yaml


class Configuration(object):
    """A class to encapsulate a single configuration."""

    _HEADER = '# Generated file, do not edit'

    def __init__(self, django_directory_path: str):
        """Initialize a configuration object from a Django project directory.

        It checks if the configuration file exists in the Django project
        directory. If it exists, then the data from that configuration file will
        be loaded. Otherwise a new configuration file will be created by the
        "save" method in the provided directory.

        Args:
            django_directory_path: Absolute path of the Django project
                directory.

        Raises:
            ValueError: If the given Django project directory is invalid.
        """
        if not os.path.isdir(django_directory_path):
            raise ValueError('[{}] is not a valid directory path.'.format(
                django_directory_path))
        self._config_path = os.path.join(django_directory_path, '.config.yaml')
        if os.path.exists(self._config_path):
            with open(self._config_path) as config_file:
                self._data = yaml.load(config_file, Loader=yaml.FullLoader)
        else:
            self._data = {}

    def set(self, attr: str, value: Any):
        """Set value of an attribute.

        Args:
            attr: The attribute name we want to set value for.
            value: Value to set for the attribute.
        """
        self._data[attr] = value

    def save(self):
        """Generate the configuration file in yaml format."""
        yaml_text = '\n'.join(
            [self._HEADER,
             yaml.dump(self._data, default_flow_style=False)])
        with open(self._config_path, 'w') as config_file:
            config_file.write(yaml_text)

    def get(self, attr: str) -> Optional[Any]:
        """Get the value of the specified attribute.

        Args:
            attr: The attribute name we want to get value from.

        Returns:
            Value of the specified attribute if it exist. Otherwise returns
                None.
        """
        return self._data.get(attr)
