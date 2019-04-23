# Deploy an existing Django application

This guide will walk you through the steps need to deploy an existing
Django application.

## Before you begin

Before running this guide, you must install the Cloud SDK, Cloud SQL Proxy.

1. Download and install the
   [Cloud SDK](https://cloud.google.com/sdk/docs/quickstarts)

2. Download and install the
   [Cloud SQL Proxy](https://cloud.google.com/sql/docs/mysql/connect-admin-proxy#install)

3. Download and install [Docker](https://docs.docker.com/install/overview/)
   (any edition)

4. Prepare your environment for Python development. You have the Python 3.5 or
   later, pip and virtualenv installed on your system. For instructions, refer
   to the [Python Development Environment Setup Guide](https://cloud.google.com/python/setup).

5. If you don't already one, you need to create a
   [Google Cloud Platform billing account](https://console.cloud.google.com/billing).
   If you are new to Google Cloud Platform, you may be able to take advantage of
   a [free trial](https://cloud.google.com/free/).

## Types of deployment

When deploying your Django application, you can choose which Google serving
technology to use:

### App Engine Standard Environment

A serverless deployment environment that requires minimal configuration and
no server maintenance
[[learn more]](https://cloud.google.com/appengine/).

### Google Kubernetes Engine

A managed container environment that allows extensive customization of the
application's execution environment
[[learn more]](https://cloud.google.com/kubernetes-engine/).

## Setup Django Deploy

1. Change directory to your Django application:

   ```bash
   cd <path/to/your/Django/application>
   ```

#### If you are already using virtual environment for your Django application

2. Activate your existing virtual environment:

   ```bash
   source <virtualenv_name>/bin/activate
   ```

3. Install Django Deploy

   ```bash
   pip install django-cloud-deploy
   ```

#### If you do not use virtual environment for your Django application

2. Create a new virtual environment to run Django Deploy:

   ```bash
   virtualenv -p python3 venv
   ```

3. Activate the new virtual environment:

   ```bash
   source venv/bin/activate
   ```

4. Install Django Deploy

   ```bash
   pip install django-cloud-deploy
   ```

5. Install dependencies of your Django application:

   ```bash
   pip install -r <path/to/your/requirements.txt>
   ```

## Deploy your Django application

1. Start Django Deploy to create and deploy a new Django application.

   When using App Engine:

   ```bash
   django-cloud-deploy cloudify --backend=gae
   ```

   When using Google Kubernetes Engine:

   ```bash
   django-cloud-deploy cloudify --backend=gke
   ```

   After running one of the above commands, you should see:
   ```bash
   12 steps to setup your new project
   ...
   ```

2. Follow the prompts displayed in the terminal. Make sure that you remember
   the following information:
    - the database password for the default user
    - the username and password for the
      [Django admin site](https://docs.djangoproject.com/en/2.2/ref/contrib/admin/)

3. Once you have answered all of the prompts, your new Django project will be
   deployed.

   At the end of the process, you will see:
   ```
   Your app is running at <url>
   ```

4. Open `<url>` in your browser to see your application running.


## Redeploying

When you are done testing your code locally, you can redeploy to the cloud.

1. Start Django Deploy to update your application:

   ```bash
   django-cloud-deploy update
   ```

   After running the above commands, you should see:
   ```bash
   3 steps to update your new project
   ...
   ```

2. Follow the prompts displayed in the terminal.

3. Once you have answered all of the prompts, your Django project will be
   updated.

   At the end of the process, you will see:
   ```
   Your app is running at <url>
   ```

4. Open `<url>` in your browser to see your updated application running.

## Clean up
To avoid incurring charges to your GCP account for the resources used in this
guide:

1. In the GCP Console, go to the
   [Projects page](https://console.cloud.google.com/iam-admin/projects).

2. In the project list, select the project you want to delete and click
   **Delete**.

3. In the dialog, type the project ID, and then click **Shut down** to delete
   the project.
