# Building a new Django application

This guide will walk you through the steps need to create and deploy a new
Django application. It will then show you how you can modify the application
and then redeploy it.

## Before you begin

Before running this guide, you must install the Cloud SDK, Cloud SQL Proxy
and setup your development environment.

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

1. Start Django Deploy to create and deploy a new Django application.

   When using App Engine:

   ```bash
   django-cloud-deploy new --backend=gae
   ```

   When using Google Kubernetes Engine:

   ```bash
   django-cloud-deploy new --backend=gke
   ```

   After running one of the above commands, you should see:
   ```bash
   11 steps to setup your new project
   ...
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

## Test the application

You can test your application locally using the built-in
[Django development server](https://docs.djangoproject.com/en/2.1/intro/tutorial01/#the-development-server).

1. Change into your project's root directory (the one containing the file
   `manage.py`):

   ```bash
   cd <project root directory>
   ```

2. Apply the needed [database migrations](https://docs.djangoproject.com/en/2.1/topics/migrations/):

   ```bash
   python manage.py migrate
   ```

3. Start the local development server with the following command:

   ```bash
   python manage.py runserver
   ```

4. View the site running on your computer at
[http://127.0.0.1:8000/](http://127.0.0.1:8000/). You should see this text in
your browser:

    **Hello from the Cloud**

## Make a change

You can leave the development server running while you develop your
application. The development server reloads your code as needed so you don't
need to restart it for your changes to take effect. Note that not all changes
will be detected (for example adding a new file), so you should restart the
development server if your changes don't appear.

1. Try it now: Leave the development server running, then open
   `<app name>/views.py`. You should see code like this:

   ```python
     def index(request):
       return HttpResponse("<h1>Hello from the Cloud!</h1>")
   ```

2. Change `"<h1>Hello from the Cloud!</h1>"` to some HTML of your choosing.

3. Reload [http://127.0.0.1:8000/](http://127.0.0.1:8000/) to see the results.


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
