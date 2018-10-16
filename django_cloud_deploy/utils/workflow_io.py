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

import abc
import getpass

import typing
from typing import List


class IO(abc.ABC):
    """
  Workflow uses the classes that follow this interface to for input/output.
  """

    def __init__(self):
        pass

    @abc.abstractmethod
    def ask(self, question: str):
        """Asks the user the question and returns an answer.

    Args:
      question: Message to tell the user
    Returns:
      The answer the user gave in a string format.
    """
        pass

    @abc.abstractmethod
    def tell(self, msg: str):
        """Tells the user the given message.

    Args:
      msg: Message to tell the user
    """
        pass


class Workflow(object):
    """
  This class is meant to use an underlying IO class to interact with the user.
  This gives flexibility when wanting to add additional logic regarding IO.
  It also allows us for simplified testing.
  """

    def __init__(self, io: IO):
        self.io = io

    def ask_password(self,
                     predicate: typing.Callable = lambda x: True,
                     error_msg: str = 'Invalid Password') -> str:
        """Ask user to provide a password."""
        while True:
            password1 = self.io.ask('Password:', hide=True)
            password2 = self.io.ask('Password (Again):', hide=True)

            if password1 != password2:
                self.io.tell('Password does not match. Please try again.')
                continue
            if not predicate(password1):
                self.io.tell(error_msg)
                continue
            return password1

    def ask(self,
            question: str,
            default_value: str = '',
            predicate: typing.Callable = lambda x: True,
            error_msg: str = 'Invalid Answer') -> str:
        """Uses underlying IO object to send output and retrieve input from user.

    default_value is returned if user just press Enter and provide nothing.
    Args:
      question: Question to ask the user.
      default_value: Default value to return.
      predicate: Function to check if input is valid.
      error_msg: Message to display to the user if input failed predicate.

    Returns:
      The input the user passed.
    """

        answer = self.io.ask(question)
        if not answer:
            return default_value

        while not predicate(answer):
            self.io.tell(error_msg)
            answer = self.io.ask(question)
            if not answer:
                return default_value

        return answer

    def tell(self, msg):
        """Uses underlying IO object to send output to user.

    Args:
      msg:  Message to tell the user

    """
        self.io.tell(msg)


class Console(IO):
    """
  Uses the console to interact with the user. See IO for method docs.
  """

    def ask(self, question: str, hide: bool = False) -> str:
        if hide:
            return getpass.getpass(question)
        else:
            return input(question)

    def tell(self, msg: str):
        print(msg)


class Test(IO):
    """
  This allow us to test the I/O by using arrays to store questions/answers
  When using this class, pass the answers in the order that the questions will
  be asked.This does require you to know what the workflow/related answers will
  be for every test.
  """

    def __init__(self, answers: List[str]):
        super().__init__()
        self.output = []
        self.answers = answers

    def ask(self, question: str, hide: bool = False) -> str:
        """
    Logs the history of questions in the order they were asked and returns
    answer in the order that they were given. Expects <= len(answers) times to
    be called in its lifetime.

    Args:
      question:

    Returns:
      The corresponding Nth answer
    """
        del hide  # Unused by ask
        self.output.append(question)
        return self.answers.pop()

    def tell(self, msg: str):
        """Logs the history of messages."""
        self.output.append(msg)
