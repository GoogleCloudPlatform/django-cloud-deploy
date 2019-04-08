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
import contextlib
import datetime
import getpass
import os
import re
import sys
import threading
import time
import typing

import progressbar


class _ProgressBar(object):
    """A progress bar showing status of a task.

    Output of the progress bar will be like the following:
        <message>|██████████∙∙∙∙∙∙∙∙| (ETA:  0:00:05)
    """

    def __init__(self,
                 expect_time: int,
                 message: str,
                 fd: typing.TextIO = sys.stderr,
                 tty: bool = True,
                 width: int = 80):
        """Constructor of the class.

        It will take "expect_time" seconds for the progress bar to go from 0%
        to 100%. If the task takes shorter than "expect time", the progress bar
        will directly go to 100%.

        Args:
            expect_time: How long the progress bar is going to run.
                (In seconds).
            message: A prefix of the progress bar showing what it is about.
            fd: The file (probably a terminal) to write progress data to.
            tty: Whether the progress bar is being used in a terminal.
            width: Width of the whole progress bar, including the prefix and
                suffix.
        """
        self._expect_time = expect_time
        self._message = message
        self._fd = fd
        self._tty = tty
        self._bar = None
        self._thread = None
        self._bar_lock = None
        self._start_time = None  # The time that the start() method was called.

        if self._tty:
            widgets = [
                self._message,
                progressbar.Bar(marker='█', fill='∙'), ' (',
                progressbar.ETA(), ') '
            ]
            # The bar will tick every 0.5 seconds.
            # term_width define width of the whole progress bar, including the
            # prefix and suffix.
            self._bar = progressbar.ProgressBar(widgets=widgets,
                                                max_value=expect_time * 2,
                                                term_width=width,
                                                fd=self._fd)

            self._thread = threading.Thread(target=self._run)
            self._bar_lock = threading.Lock()
        else:
            # Not showing progress bar when not writing to an interactive
            # console. This is because the progress bar might not show properly.
            self._fd.write('{} (ETA: {} seconds)\n'.format(
                self._message, self._expect_time))

    def start(self):
        self._start_time = datetime.datetime.now()
        if self._tty:
            self._thread.start()

    def finish(self):
        """Make progress bar go to the end.

        This is useful when the task takes shorter than the expect time to
        finish.
        """
        if self._tty:
            with self._bar_lock:
                # Go to the end of progress bar.
                self._bar.update(self._expect_time * 2)
                self._bar.finish()
        else:
            # Format the output like:
            # Updating FlimFlam (ETA: 120 seconds)
            #                -> (actual: 74 seconds)
            self._fd.write('{0} -> (actual: {1:.0f} seconds)\n'.format(
                ' ' * (len(self._message) - len(' ->')),
                (datetime.datetime.now() - self._start_time).total_seconds()))

    def _run(self):
        """The function to update progress bar."""
        # TODO: Find a way to handle tasks take longer than expectation.
        # Right now the progress bar will stuck.
        with self._bar_lock:
            self._bar.start()
        for i in range(self._expect_time * 2):
            with self._bar_lock:
                # The progress of the bar can be modified by _finish method.
                # This part is to handle that case.
                if self._bar.value == self._expect_time * 2:
                    return
                if self._tty:
                    self._bar.update(i)
            time.sleep(0.5)


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
        """Prompt the user for a password and return the result."""


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
        print(*(self._replace_html_tags(a, sys.stdout.fileno()) for a in args),
              file=sys.stderr)

    def ask(self, prompt=None):
        return input(self._replace_html_tags(prompt, sys.stdout.fileno()))

    def getpass(self, prompt=None):
        """Prompt the user for a password and return the result."""
        return getpass.getpass(prompt)

    @contextlib.contextmanager
    def progressbar(self, expect_time: int, message: str):
        """A context manager that shows a progress bar.

        Output of the progress bar will be like the following:
            <message>|██████████∙∙∙∙∙∙∙∙| (ETA:  0:00:05)

        If the task ends earlier than expected, the progress bar will directly
        go to the end.

        Args:
            expect_time: How long the progress bar is going to run.
                (In seconds).
            message: A prefix of the progress bar showing what it is about.

        Yields:
            None
        """

        is_tty = os.isatty(sys.stderr.fileno())
        progress_bar = _ProgressBar(expect_time,
                                    message,
                                    sys.stderr,
                                    tty=is_tty)
        try:
            progress_bar.start()
            yield
        finally:
            progress_bar.finish()


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
        """Prompt the user for a password and return the result."""
        self.passwords.append(prompt)
        return self.password_answers.pop(0)
