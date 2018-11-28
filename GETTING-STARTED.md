# Getting Started

## Setup and Installation

### Prerequisites

In order to use **Django Deploy**, you must first install the following dependencies:
- [Python](https://www.python.org/downloads/) 3.5 or higher
- [virtualenv](https://virtualenv.pypa.io/en/stable/installation/)
- [Docker](https://docs.docker.com/install/overview/) (any edition)
- [Google Cloud SDK](https://cloud.google.com/sdk/docs/quickstarts)
- [Cloud SQL Proxy](https://cloud.google.com/sql/docs/mysql/connect-admin-proxy#install)

You will also need a
[Google Cloud Platform billing account](https://cloud.google.com/billing/docs/how-to/manage-billing-account).
If you don't already have one, you can
[create one](https://console.cloud.google.com/billing). If you are new to
Google Cloud Platform, you may be able to take advantage of a
[free trial](https://cloud.google.com/free/).

### Installation

Once the [prerequisites](#Prerequisites) have been installed, you can install
`Django Deploy` from the command line:

```bash
$ virtualenv -p python3 django-deploy # requires Python 3.5 or higher, check with `python3 --version`
$ source django-deploy/bin/activate
$ pip install django-cloud-deploy
```

## Creating a New Project

You can create a new Django project after completing the
[Setup and Installation steps](#Setup-and-Installation) and running this
command:
```bash
$ django-cloud-deploy new
```

Follow the prompts displayed in the terminal. Make sure that you remember the
following information:

 - the database password for the default user
 - the directory location of the project source
 - the username and password for the
   [Django admin site](https://docs.djangoproject.com/en/2.1/ref/contrib/admin/)

During the configuration process, you will be prompted, in your web browser, to
associate your Google account with the
[Google Cloud SDK](https://cloud.google.com/sdk).

You will also be prompted to associate the project with a
[Google Cloud Platform billing account](https://cloud.google.com/billing/docs/how-to/modify-project#enable_billing_for_a_project).
If you don't already have a billing account setup then you will have the option
of creating one in your web browser.

Once you have answered all of the prompts, your new Django project will be
created and deployed to
[Google Kubernetes Engine](https://cloud.google.com/kubernetes-engine/). This
can take up to 20 minutes and will finish with a message like:

```
Your app is running at <url>
```

You can open `<url>` in your browser to see your application running.

## Updating Your Project

You can make any change that you want to your application and redeploy it.

For example, open `<app name>/views.py` and you should see this code:

```python
def index(request):
    return HttpResponse("<h1>Hello from the Cloud!</h1>")
```

Change the message from `"<h1>Hello from the Cloud!</h1>"` to something of your
choosing.

You can test your changes with
[manage.py](https://docs.djangoproject.com/en/2.1/ref/django-admin/#runserver):
```bash
$ python <project path>/manage.py runserver
```

When you are satisfied with your changes, you can deploy your changes to the
cloud with:
```bash
$ django-cloud-deploy update --project-path=<project path>
```

Follow the prompts displayed in the terminal.

During the update process, you may be prompted, in your web browser, to
associate your Google account with the
[Google Cloud SDK](https://cloud.google.com/sdk).

Once you have answered all of the prompts, your Django project will be
updated. This can take up to 10 minutes and will finish with a message like:

```
Your app is running at <url>
```

You can open `<url>` in your browser to see your updated application.
