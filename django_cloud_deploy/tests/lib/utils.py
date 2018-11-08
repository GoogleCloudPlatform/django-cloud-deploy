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

import datetime
import random
import string

TIMESTAMP_FORMAT = '%Y%m%d%H%M%S'


def get_resource_name(resource_type: str = '',
                      hash_len: int = 4,
                      timestamp_format: str = TIMESTAMP_FORMAT,
                      delimiter: chr = '-') -> str:
    """Generate resource names as TYPE-YYYYMMDD-HHMMSS-HASH.

    This function is useful to avoid operations on the same resource when
    running integration tests simultaneously.

    Args:
        resource_type: Type of the resource which needs to generated name.
        hash_len: The length of hash at the end of generated name.
        timestamp_format: The timestamp format used to generate the name.
        delimiter: The character to delimit the random strings.

    Returns:
        Generated name with the format mentioned above.
    """

    timestamp = datetime.datetime.utcnow().strftime(timestamp_format)
    hash_str = ''.join([
        random.SystemRandom().choice(string.ascii_lowercase + string.digits)
        for _ in range(hash_len)
    ])
    return delimiter.join([resource_type, timestamp, hash_str])
