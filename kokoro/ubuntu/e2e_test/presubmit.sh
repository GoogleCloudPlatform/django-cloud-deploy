#!/bin/bash
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

# Fail on any error.
set -e
# Display commands being run.
set -x

export GOOGLE_APPLICATION_CREDENTIALS="$KOKORO_GFILE_DIR/cloud-django-integration-test-key.json"

# The chrome driver is required to be exist in $PATH for using selenium
sudo cp $KOKORO_GFILE_DIR/chromedriver /usr/local/bin/.

gcloud auth activate-service-account --key-file=$GOOGLE_APPLICATION_CREDENTIALS

sudo wget https://dl.google.com/cloudsql/cloud_sql_proxy.linux.amd64 -O /usr/local/bin/cloud_sql_proxy
sudo chmod +x /usr/local/bin/cloud_sql_proxy

cd $KOKORO_ARTIFACTS_DIR/github/django-cloud-deploy
source kokoro/ubuntu/common.sh
nox -f django_cloud_deploy/nox.py -s e2e_test