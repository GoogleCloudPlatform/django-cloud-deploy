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
"""Tests for django_cloud_deploy.cli.prompt."""

import random
import tempfile

from absl.testing import absltest
from absl.testing import parameterized

from django_cloud_deploy.cli import io
from django_cloud_deploy.cli import prompt


class GoogleCloudProjectNamePromptTest(absltest.TestCase):
    """Tests for prompt.GoogleCloudProjectNamePrompt."""

    def test_prompt(self):
        test_io = io.TestIO()

        test_io.answers.append('My Project')
        name = prompt.GoogleCloudProjectNamePrompt.prompt(test_io, '[1/2]', {})
        self.assertEqual(name, 'My Project')
        self.assertEqual(len(test_io.answers), 0)  # All answers used.

    def test_prompt_default(self):
        test_io = io.TestIO()

        test_io.answers.append('')
        name = prompt.GoogleCloudProjectNamePrompt.prompt(test_io, '[1/2]', {})
        self.assertEqual(name, 'Django Project')
        self.assertEqual(len(test_io.answers), 0)  # All answers used.

    def test_prompt_bad_name(self):
        test_io = io.TestIO()

        test_io.answers.append('S')
        test_io.answers.append('Long Enough')
        name = prompt.GoogleCloudProjectNamePrompt.prompt(test_io, '[1/2]', {})
        self.assertEqual(name, 'Long Enough')
        self.assertEqual(len(test_io.answers), 0)  # All answers used.

    def test_validate_success(self):
        prompt.GoogleCloudProjectNamePrompt.validate('My Project')

    def test_validate_short(self):
        with self.assertRaisesRegex(ValueError, 'XXX'):
            prompt.GoogleCloudProjectNamePrompt.validate('XXX')


class DjangoProjectNamePromptTest(absltest.TestCase):
    """Tests for prompt.DjangoProjectNamePrompt."""

    def test_prompt(self):
        test_io = io.TestIO()

        test_io.answers.append('djangoproject')
        name = prompt.DjangoProjectNamePrompt.prompt(test_io, '[1/2]', {})
        self.assertEqual(name, 'djangoproject')
        self.assertEqual(len(test_io.answers), 0)  # All answers used.

    def test_prompt_default(self):
        test_io = io.TestIO()

        test_io.answers.append('')
        name = prompt.DjangoProjectNamePrompt.prompt(test_io, '[1/2]', {})
        self.assertEqual(name, 'mysite')
        self.assertEqual(len(test_io.answers), 0)  # All answers used.

    def test_prompt_bad_name(self):
        test_io = io.TestIO()

        test_io.answers.append('5')
        test_io.answers.append('djangoproject')
        name = prompt.DjangoProjectNamePrompt.prompt(test_io, '[1/2]', {})
        self.assertEqual(name, 'djangoproject')
        self.assertEqual(len(test_io.answers), 0)  # All answers used.

    def test_validate_success(self):
        prompt.DjangoProjectNamePrompt.validate('mysite5')

    def test_validate_non_identifier(self):
        with self.assertRaisesRegex(ValueError, '5'):
            prompt.DjangoProjectNamePrompt.validate('5')


class DjangoAppNamePromptTest(absltest.TestCase):
    """Tests for prompt.DjangoAppNamePrompt."""

    def test_prompt(self):
        test_io = io.TestIO()

        test_io.answers.append('djangoapp')
        name = prompt.DjangoAppNamePrompt.prompt(test_io, '[1/2]', {})
        self.assertEqual(name, 'djangoapp')
        self.assertEqual(len(test_io.answers), 0)  # All answers used.

    def test_prompt_default(self):
        test_io = io.TestIO()

        test_io.answers.append('')
        name = prompt.DjangoAppNamePrompt.prompt(test_io, '[1/2]', {})
        self.assertEqual(name, 'home')
        self.assertEqual(len(test_io.answers), 0)  # All answers used.

    def test_prompt_bad_name(self):
        test_io = io.TestIO()

        test_io.answers.append('5')
        test_io.answers.append('djangoapp')
        name = prompt.DjangoAppNamePrompt.prompt(test_io, '[1/2]', {})
        self.assertEqual(name, 'djangoapp')
        self.assertEqual(len(test_io.answers), 0)  # All answers used.

    def test_validate_success(self):
        prompt.DjangoAppNamePrompt.validate('myapp7')

    def test_validate_non_identifier(self):
        with self.assertRaisesRegex(ValueError, '5'):
            prompt.DjangoAppNamePrompt.validate('5')


class DjangoSuperuserLoginPromptTest(absltest.TestCase):
    """Tests for prompt.DjangoSuperuserLoginPrompt."""

    def test_prompt(self):
        test_io = io.TestIO()

        test_io.answers.append('myusername')
        name = prompt.DjangoSuperuserLoginPrompt.prompt(test_io, '[1/2]', {})
        self.assertEqual(name, 'myusername')
        self.assertEqual(len(test_io.answers), 0)  # All answers used.

    def test_prompt_default(self):
        test_io = io.TestIO()

        test_io.answers.append('')
        name = prompt.DjangoSuperuserLoginPrompt.prompt(test_io, '[1/2]', {})
        self.assertEqual(name, 'admin')
        self.assertEqual(len(test_io.answers), 0)  # All answers used.

    def test_prompt_bad_name(self):
        test_io = io.TestIO()

        test_io.answers.append('My Name')
        test_io.answers.append('myname')
        name = prompt.DjangoSuperuserLoginPrompt.prompt(test_io, '[1/2]', {})
        self.assertEqual(name, 'myname')
        self.assertEqual(len(test_io.answers), 0)  # All answers used.

    def test_validate_success(self):
        prompt.DjangoSuperuserLoginPrompt.validate('myapp7')

    def test_validate_non_identifier(self):
        with self.assertRaisesRegex(ValueError, 'My Name'):
            prompt.DjangoSuperuserLoginPrompt.validate('My Name')


class DjangoSuperuserEmailPromptTest(absltest.TestCase):
    """Tests for prompt.DjangoSuperuserEmailPrompt."""

    def test_prompt(self):
        test_io = io.TestIO()

        test_io.answers.append('admin@example.com')
        email = prompt.DjangoSuperuserEmailPrompt.prompt(test_io, '[1/2]', {})
        self.assertEqual(email, 'admin@example.com')
        self.assertEqual(len(test_io.answers), 0)  # All answers used.

    def test_prompt_default(self):
        test_io = io.TestIO()

        test_io.answers.append('')
        email = prompt.DjangoSuperuserEmailPrompt.prompt(test_io, '[1/2]', {})
        self.assertEqual(email, 'test@example.com')
        self.assertEqual(len(test_io.answers), 0)  # All answers used.

    def test_prompt_bad_address(self):
        test_io = io.TestIO()

        test_io.answers.append('Not An Email Address')
        test_io.answers.append('admin@example.com')
        email = prompt.DjangoSuperuserEmailPrompt.prompt(test_io, '[1/2]', {})
        self.assertEqual(email, 'admin@example.com')
        self.assertEqual(len(test_io.answers), 0)  # All answers used.

    def test_validate_success(self):
        prompt.DjangoSuperuserEmailPrompt.validate('admin@example.com')

    def test_validate_non_identifier(self):
        with self.assertRaisesRegex(ValueError, 'Not An Email Address'):
            prompt.DjangoSuperuserEmailPrompt.validate('Not An Email Address')


class ProjectIdPromptTest(parameterized.TestCase):
    """Tests for prompt.ProjectIdPrompt."""

    @parameterized.parameters(''.join(
        chr(random.randint(0, 256))
        for _ in range(random.randint(1, 60)))
                              for _ in range(1000))
    def test_generates_valid_project_ids(self, project_name):
        test_io = io.TestIO()
        test_io.answers.append('')
        project_id = prompt.ProjectIdPrompt._generate_default_project_id(
            project_name)
        prompt.ProjectIdPrompt.validate(project_id)

    def test_prompt(self):
        test_io = io.TestIO()

        test_io.answers.append('projectid-123')
        project_id = prompt.ProjectIdPrompt.prompt(test_io, '[1/2]', {})
        self.assertEqual(project_id, 'projectid-123')
        self.assertEqual(len(test_io.answers), 0)  # All answers used.

    def test_prompt_default(self):
        test_io = io.TestIO()

        test_io.answers.append('')
        project_id = prompt.ProjectIdPrompt.prompt(test_io, '[1/2]', {})
        self.assertRegex(project_id, 'django-\d{6}')
        self.assertEqual(len(test_io.answers), 0)  # All answers used.

    def test_prompt_default_project_name(self):
        test_io = io.TestIO()

        test_io.answers.append('')
        project_id = prompt.ProjectIdPrompt.prompt(
            test_io, '[1/2]', {'project_name': 'My Project'})
        self.assertRegex(project_id, 'my-project-\d{6}')
        self.assertEqual(len(test_io.answers), 0)  # All answers used.

    def test_prompt_bad_id(self):
        test_io = io.TestIO()

        test_io.answers.append('2short')
        test_io.answers.append('long-enough')
        project_id = prompt.ProjectIdPrompt.prompt(test_io, '[1/2]', {})
        self.assertEqual(project_id, 'long-enough')
        self.assertEqual(len(test_io.answers), 0)  # All answers used.


class DjangoFilesystemPathTest(parameterized.TestCase):
    """Tests for prompt.DjangoFilesystemPath."""

    def test_prompt(self):
        test_io = io.TestIO()

        test_io.answers.append('/tmp/foo')
        path = prompt.DjangoFilesystemPath.prompt(test_io, '[1/2]', {})
        self.assertEqual(path, '/tmp/foo')
        self.assertEqual(len(test_io.answers), 0)  # All answers used.

    @parameterized.parameters('y', 'Y')
    def test_prompt_existing_path(self, yes_replace_character):
        test_io = io.TestIO()

        with tempfile.NamedTemporaryFile() as f:
            test_io.answers.append(f.name)
            test_io.answers.append(yes_replace_character)
            path = prompt.DjangoFilesystemPath.prompt(test_io, '[1/2]', {})
            self.assertEqual(path, f.name)
            self.assertEqual(len(test_io.answers), 0)  # All answers used.

    @parameterized.parameters('', 'n', 'N')
    def test_prompt_existing_path_new_path(self, no_replace_character):
        test_io = io.TestIO()

        with tempfile.NamedTemporaryFile() as f:
            test_io.answers.append(f.name)
            test_io.answers.append(no_replace_character)
            test_io.answers.append('/tmp/newname')
            path = prompt.DjangoFilesystemPath.prompt(test_io, '[1/2]', {})
            self.assertEqual(path, '/tmp/newname')
            self.assertEqual(len(test_io.answers), 0)  # All answers used.

    def test_prompt_default(self):
        test_io = io.TestIO()

        test_io.answers.append('')
        prompt.DjangoFilesystemPath.prompt(test_io, '[1/2]', {})
        self.assertEqual(len(test_io.answers), 0)  # All answers used.

    def test_prompt_default_project_name(self):
        test_io = io.TestIO()

        test_io.answers.append('')
        path = prompt.DjangoFilesystemPath.prompt(
            test_io, '[1/2]', {'project_name': 'Project Name'})
        self.assertIn('project-name', path)
        self.assertEqual(len(test_io.answers), 0)  # All answers used.


class PostgresPasswordPromptTest(parameterized.TestCase):
    """Tests for prompt.PostgresPasswordPrompt."""

    def test_prompt(self):
        test_io = io.TestIO()

        test_io.password_answers.append('mypass32')
        test_io.password_answers.append('mypass32')
        password = prompt.PostgresPasswordPrompt.prompt(test_io, '[1/2]', {})
        self.assertEqual(password, 'mypass32')
        self.assertEqual(len(test_io.password_answers), 0)  # All answers used.

    def test_bad_confirmation(self):
        test_io = io.TestIO()

        test_io.password_answers.append('mypass32')
        test_io.password_answers.append('mypass64')
        test_io.password_answers.append('secondtry2')
        test_io.password_answers.append('secondtry2')
        password = prompt.PostgresPasswordPrompt.prompt(test_io, '[1/2]', {})
        self.assertEqual(password, 'secondtry2')
        self.assertEqual(len(test_io.password_answers), 0)  # All answers used.

    def test_bad_password(self):
        test_io = io.TestIO()

        test_io.password_answers.append(' ')
        test_io.password_answers.append('secondtry2')
        test_io.password_answers.append('secondtry2')
        password = prompt.PostgresPasswordPrompt.prompt(test_io, '[1/2]', {})
        self.assertEqual(password, 'secondtry2')
        self.assertEqual(len(test_io.password_answers), 0)  # All answers used.


class DjangoSuperuserPasswordPromptTest(parameterized.TestCase):
    """Tests for prompt.DjangoSuperuserPasswordPrompt."""

    def test_prompt(self):
        test_io = io.TestIO()

        test_io.password_answers.append('mypass32')
        test_io.password_answers.append('mypass32')
        password = prompt.DjangoSuperuserPasswordPrompt.prompt(
            test_io, '[1/2]', {})
        self.assertEqual(password, 'mypass32')
        self.assertEqual(len(test_io.password_answers), 0)  # All answers used.

    def test_prompt_django_superuser_login(self):
        test_io = io.TestIO()

        test_io.password_answers.append('mypass32')
        test_io.password_answers.append('mypass32')
        password = prompt.DjangoSuperuserPasswordPrompt.prompt(
            test_io, '[1/2]', {'django_superuser_login': 'guido'})
        self.assertIn('guido', ' '.join(c for (c, *a) in test_io.tell_calls))
        self.assertEqual(password, 'mypass32')
        self.assertEqual(len(test_io.password_answers), 0)  # All answers used.

    def test_bad_confirmation(self):
        test_io = io.TestIO()

        test_io.password_answers.append('mypass32')
        test_io.password_answers.append('mypass64')
        test_io.password_answers.append('secondtry2')
        test_io.password_answers.append('secondtry2')
        password = prompt.DjangoSuperuserPasswordPrompt.prompt(
            test_io, '[1/2]', {})
        self.assertEqual(password, 'secondtry2')
        self.assertEqual(len(test_io.password_answers), 0)  # All answers used.

    def test_bad_password(self):
        test_io = io.TestIO()

        test_io.password_answers.append(' ')
        test_io.password_answers.append('secondtry2')
        test_io.password_answers.append('secondtry2')
        password = prompt.DjangoSuperuserPasswordPrompt.prompt(
            test_io, '[1/2]', {})
        self.assertEqual(password, 'secondtry2')
        self.assertEqual(len(test_io.password_answers), 0)  # All answers used.


if __name__ == '__main__':
    absltest.main()
