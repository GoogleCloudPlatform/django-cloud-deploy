# Quickstart for deploying a Django application on App Engine

This quickstart shows you how to create a small Django application that
displays a simple message.

## Before you begin

Before running this quickstart, you must install the Cloud SDK, Cloud SQK Proxy
and setup your development environment.

1. Download and install the [Cloud SDK](https://cloud.google.com/sdk/docs/quickstarts)

2. Download and install the [Cloud SQL Proxy](https://cloud.google.com/sql/docs/mysql/connect-admin-proxy#install)

3. Prepare your environment for Python development. You have the Python 3.5 or
   later, pip and virtualenv installed on your system. For instructions, refer
   to the [Python Development Environment Setup Guide](https://cloud.google.com/python/setup).

4. If you don't already one, you need to create a 
   [Google Cloud Platform billing account](https://console.cloud.google.com/billing).
   If you are new to Google Cloud Platform, you may be able to take advantage of
   a [free trial](https://cloud.google.com/free/).

## Setup Django Deploy

Create a development environment and install Django Deploy into it.

1. Create a new virtual environment to run Django Deploy:

```bash
virtualenv -p python3 django-deploy
```

2. Activate the new virtual environment:

```bash
source django-deploy/bin/activate
```

3. Install Django Deploy

```bash
 pip install django-cloud-deploy
```

## Deploy a new Django application

1. Start Django Deploy to create and deploy a new Django application on App
   Engine

```bash
django-cloud-deploy new
```

You should see:
```bash
11 steps to setup your new project
```

2. Follow the prompts displayed in the terminal. Make sure that you remember
   the following information:
 - the database password for the default user
 - the directory location of the project source
 - the username and password for the
   [Django admin site](https://docs.djangoproject.com/en/2.1/ref/contrib/admin/)

3. Once you have answered all of the prompts, your new Django project will be
created and deployed.

At the end of the process, you will see:
```
Your app is running at <url>
```

4. Open `<url>` in your browser to see your application running.

## Clean up
To avoid incurring charges to your GCP account for the resources used in this
quickstart:

1. In the GCP Console, go to the [Projects page](https://console.cloud.google.com/iam-admin/projects).

2. In the project list, select the project you want to delete and click
   **Delete**.

3. In the dialog, type the project ID, and then click **Shut down** to delete
   the project.

