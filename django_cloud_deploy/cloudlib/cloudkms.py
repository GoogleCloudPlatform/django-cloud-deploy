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
"""Manages Google Cloud Key Management resources.

See https://cloud.google.com/kms/docs/
"""

import base64
from typing import Optional, List

from googleapiclient import discovery
from googleapiclient import errors
from google.auth import credentials


class CloudKmsError(Exception):
    """An error raised when failed to make a Cloud KMS request."""
    pass


class CloudKmsClient(object):
    """A class for managing Google Cloud Key Management resources."""

    def __init__(self, cloudkms_service: discovery.Resource):
        self._cloudkms_service = cloudkms_service

    @classmethod
    def from_credentials(cls, credentials: credentials.Credentials):
        return cls(
            discovery.build('cloudkms',
                            'v1',
                            credentials=credentials,
                            cache_discovery=False))

    def create_keyring(self,
                       project_id: str,
                       name: str,
                       location: str = 'global'):
        """Create a cryptographic key ring.

        A key ring is a toplevel logical grouping of cryptographic keys.

        Args:
            project_id: The id of the project where you want to create the key
                ring.
            name: Name of the key ring.
            location: Where you want to make the key ring available.
        """
        parent = 'projects/{}/locations/{}'.format(project_id, location)
        keyring_rsrc = self._cloudkms_service.projects().locations().keyRings()
        request = keyring_rsrc.create(parent=parent, keyRingId=name, body={})
        request.execute(num_retries=5)

    def create_key(self,
                   project_id: str,
                   keyring_name: str,
                   key_name: str,
                   location: str = 'global'):
        """Create a cryptographic key.

        Args:
            project_id: The id of the project where you want to create the key
                ring.
            keyring_name: Name of the cryptographic key ring. A key ring is a
                toplevel logical grouping of cryptographic keys.
            key_name: Name of the cryptographic key.
            location: Where the key ring is available.
        """
        parent = 'projects/{}/locations/{}/keyRings/{}'.format(
            project_id, location, keyring_name)
        keyring_rsrc = self._cloudkms_service.projects().locations().keyRings()
        request_body = {
            'purpose': 'ENCRYPT_DECRYPT',
        }
        request = keyring_rsrc.cryptoKeys().create(parent=parent,
                                                   cryptoKeyId=key_name,
                                                   body=request_body)
        request.execute(num_retries=5)

    def list_keyrings(self, project_id: str,
                      location: str = 'global') -> Optional[List[str]]:
        """List cryptographic key rings in the given project and location.

        A key ring is a toplevel logical grouping of cryptographic keys.

        Args:
            project_id: The id of the project where you want to create the key
                ring.
            location: The location where the key rings are available.

        Returns:
            The keyrings in the given project that are available in the given
            location.

        Raises:
            CloudKmsError: When the api call does not return the expected
                response.
        """
        parent = 'projects/{}/locations/{}'.format(project_id, location)
        keyring_rsrc = self._cloudkms_service.projects().locations().keyRings()
        request = keyring_rsrc.list(parent=parent)
        try:
            response = request.execute(num_retries=5)
            if 'keyRings' not in response:
                raise CloudKmsError(
                    'Unexpected response when listing keyrings [{}]'.format(
                        response))
        except errors.HttpError as e:
            if e.resp.status == 404:
                # The given project or location does not exist
                return []
        keyring_names = [
            keyring['name'].split('/')[-1] for keyring in response['keyRings']
        ]
        return keyring_names

    def list_keys(self,
                  project_id: str,
                  keyring_name: str,
                  location: str = 'global') -> Optional[List[str]]:
        """List cryptographic keys in the given key ring.

        Args:
            project_id: The id of the project where you want to create the key
                ring.
            keyring_name: Name of the cryptographic key ring. A key ring is a
                toplevel logical grouping of cryptographic keys.
            location: The location where the given key ring is available.

        Returns:
            The keys in the given key ring.

        Raises:
            CloudKmsError: When the api call does not return the expected
                response.
        """
        parent = 'projects/{}/locations/{}/keyRings/{}'.format(
            project_id, location, keyring_name)
        keyring_rsrc = self._cloudkms_service.projects().locations().keyRings()
        request = keyring_rsrc.cryptoKeys().list(parent=parent)
        try:
            response = request.execute(num_retries=5)
            if 'cryptoKeys' not in response:
                raise CloudKmsError(
                    'Unexpected response when listing keys [{}]'.format(
                        response))
        except errors.HttpError as e:
            if e.resp.status == 404:
                # The given keyring or project or location does not exist
                return []
        key_names = [
            key['name'].split('/')[-1] for key in response['cryptoKeys']
        ]
        return key_names

    def encrypt(self,
                plaintext: str,
                project_id: str,
                key_name: str,
                keyring_name: str,
                location: str = 'global') -> Optional[str]:
        """Encrypt the given plain text using the key provided.

        Args:
            plaintext: The data to encrypt.
            project_id: The id of the project where the given key is in.
            key_name: Name of the cryptographic key.
            keyring_name: Name of the cryptographic key ring. A key ring is a
                toplevel logical grouping of cryptographic keys.
            location: The location that the keyring is available.

        Returns:
            The cipher text generated with the given plain text.

        Raises:
            CloudKmsError: When the encryption api call does not return the
                expected response.
        """
        name = 'projects/{}/locations/{}/keyRings/{}/cryptoKeys/{}'.format(
            project_id, location, keyring_name, key_name)

        # Cloud KMS api requires the plain text to be a base64 encoded string.
        b64_encoded_plaintext = base64.urlsafe_b64encode(
            plaintext.encode('utf-8')).decode('utf-8')

        keyring_rsrc = self._cloudkms_service.projects().locations().keyRings()
        request = keyring_rsrc.cryptoKeys().encrypt(
            name=name, body={'plaintext': b64_encoded_plaintext})
        response = request.execute(num_retries=5)
        if 'ciphertext' not in response:
            raise CloudKmsError(
                'Unexpected response when encrypting text "{}" [{}]'.format(
                    plaintext, response))
        return response['ciphertext']

    def decrypt(self,
                ciphertext: str,
                project_id: str,
                key_name: str,
                keyring_name: str,
                location: str = 'global') -> Optional[str]:
        """Decrypt the data that was previously encrypted with the key provided.

        Args:
            ciphertext: The encrypted data originally encrypted with the given
                key.
            project_id: The id of the project where the given key is in.
            key_name: Name of the cryptographic key.
            keyring_name: Name of the cryptographic key ring. A key ring is a
                toplevel logical grouping of cryptographic keys.
            location: The location that the keyring is available.

        Returns:
            The decrypted data generated from the given cipher text.

        Raises:
            CloudKmsError: When the decryption api call does not return the
                expected response.
        """
        name = 'projects/{}/locations/{}/keyRings/{}/cryptoKeys/{}'.format(
            project_id, location, keyring_name, key_name)
        keyring_rsrc = self._cloudkms_service.projects().locations().keyRings()
        request = keyring_rsrc.cryptoKeys().decrypt(
            name=name, body={'ciphertext': ciphertext})
        response = request.execute(num_retries=5)
        if 'plaintext' not in response:
            raise CloudKmsError(
                'Unexpected response when decrypting text "{}" [{}]'.format(
                    ciphertext, response))

        # Return value Cloud KMS api call is a base64 encoded string
        b64_encoded_ciphertext = response['plaintext']
        return base64.urlsafe_b64decode(b64_encoded_ciphertext).decode('utf-8')
