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
"""Class for managing console I/O."""

import abc
import getpass
import os
import re
import sys


class IO(abc.ABC):

    def __init__(self):
        pass

    @abc.abstractmethod
    def tell(self, *args):
        """Prints `args` to stdout.

    Args:
      args: The objects to print. For strings, the following HTML tags are
          interpreted: <b>This text in bold</b>.
    """
        pass

    @abc.abstractmethod
    def error(self, *args):
        """Prints `args` to stderr.

    Args:
      args: The objects to print. For strings, the following HTML tags are
          interpreted: <b>This text in bold</b>.
    """
        pass

    @abc.abstractmethod
    def ask(self, prompt=None):
        pass

    @abc.abstractmethod
    def getpass(self, prompt=None):
        "Prompt the user for a password and return the result."


class ConsoleIO(IO):
    BOLD = '\033[1m'
    END = '\033[0m'

    def _replace_html_tags(self, s, f):
        if isinstance(s, str):
            bold_substitution = r'\1'
            if os.isatty(f) and os.name == 'posix':
                bold_substitution = r'{0}\1{1}'.format(self.BOLD, self.END)

            return re.sub('<b>(.*?)</b>', bold_substitution, s)
        else:
            return s

    def tell(self, *args):
        print(*(self._replace_html_tags(a, sys.stdout.fileno()) for a in args))

    def error(self, *args):
        print(
            *(self._replace_html_tags(a, sys.stdout.fileno()) for a in args),
            file=sys.stderr)

    def ask(self, prompt=None):
        return input(prompt)

    def getpass(self, prompt=None):
        "Prompt the user for a password and return the result."
        return getpass.getpass(prompt)


class TestIO(IO):

    def __init__(self):
        self.tell_calls = []
        self.error_calls = []
        self.answers = []
        self.ask_prompts = []
        self.passwords = []
        self.password_answers = []

    def tell(self, *args):
        self.tell_calls.append(args)

    def error(self, *args):
        self.error_calls.append(args)

    def ask(self, prompt=None):
        self.ask_prompts.append(prompt)
        return self.answers.pop(0)

    def getpass(self, prompt=None):
        "Prompt the user for a password and return the result."
        self.passwords.append(prompt)
        return self.password_answers.pop(0)
