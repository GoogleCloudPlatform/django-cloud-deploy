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

import os
import setuptools


here = os.path.abspath(os.path.dirname(__file__))

info = {}
with open(os.path.join(here, 'django_cloud_deploy', '__version__.py')) as f:
    exec(f.read(), info)


with open(os.path.join(here, 'README.md'), 'r') as fh:
    long_description = fh.read()


install_requires = [
    'urllib3>=1.23,<2',
    'oauth2client>=4.1.2',
    'django>=2.1.5,<2.2',
    'backoff>=1.8.0',
    'jinja2>=2.10',
    'google-cloud-resource-manager>=0.28.1',
    'docker>=3.4.1',
    'kubernetes>=6.0.0',
    'google-cloud-container>=0.1.1',
    'grpcio>=1.14.1',
    'google-cloud-storage>=1.10.0',
    'pexpect>=4.6.0',
    'psycopg2-binary>=2.7.5',
    'google-api-python-client>=1.7.4',
    'google-auth-httplib2>=0.0.3',
    'google-cloud-logging>=1.8.0',
    'progressbar2>=3.38.0',
    'portpicker>=1.2.0',
    'PyYAML>=5.1',
]


setuptools.setup(
    name='django-cloud-deploy',

    version=info['__version__'],

    description='Tool to deploy a Django App onto GCP',
    long_description=long_description,
    long_description_content_type='text/markdown',

    url='https://github.com/GoogleCloudPlatform/django-cloud-deploy',

    author='Django Deploy Team',

    packages=setuptools.find_packages(),
    include_package_data=True,
    install_requires=install_requires,
    python_requires='>=3.5',

    license='Apache 2.0',
    keywords='google django cloud',

    classifiers=[
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: Unix',
        'Intended Audience :: Developers'
    ],

    entry_points={
        'console_scripts': [
            'django-cloud-deploy = django_cloud_deploy.django_cloud_deploy:main']
    },
)
