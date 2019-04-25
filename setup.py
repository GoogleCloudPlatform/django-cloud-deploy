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
    # "requests" is one of our implicit dependency, which has dependency
    # "urllib3<1.25".
    # See https://github.com/kennethreitz/requests/blob/master/setup.py#L47
    'urllib3>=1.23,<1.25',
    'oauth2client>=4.1.2',
    'django>=2.1.5',
    'backoff>=1.8.0',
    'jinja2>=2.10',
    'docker>=3.4.1',
    'kubernetes>=6.0.0',
    'grpcio>=1.14.1',
    'pexpect>=4.6.0',
    'google-api-python-client>=1.7.4',
    'google-auth-httplib2>=0.0.3',
    'progressbar2>=3.38.0',
    'portpicker>=1.2.0',
    'PyYAML>=5.1',
]


test_requires = [
    'absl-py>=0.7.1',
    'nox',
    'nox-automation>=0.19.1',
    'selenium>=3.141.0',
]


extras = {
    'test': test_requires
}


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
    extras_require=extras,
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
