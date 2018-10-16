# Usage instructions

**Django Deploy** can be used to create and then deploy new
[Django](https://www.djangoproject.com/) applications on
[Kubernetes Engine](https://cloud.google.com/kubernetes-engine/).

When run, **Django Deploy**:
1. Creates a new skeleton [Django](https://www.djangoproject.com/) project.
2. Creates a new [Google Cloud Platform project](https://cloud.google.com/resource-manager/docs/creating-managing-projects).
3. Creates a new [Cloud SQL](https://cloud.google.com/sql/docs/) instance.
4. Initializes the Cloud SQL instance with the skeleton applications schema
   (using Django's
   [migration](https://docs.djangoproject.com/en/2.1/topics/migrations/)
   facility).
5. Creates a Django
   [super user](https://docs.djangoproject.com/en/2.1/ref/django-admin/#createsuperuser).
6. Creates a new [Kubernetes Cluster](https://cloud.google.com/kubernetes-engine/docs/concepts/cluster-architecture).
7. Builds your application image and displays it to the cluster.
8. Exposes your application to the Internet using a public IP address.

## Supported Platforms

- Linux
- Mac OS X

## Prerequisites

In order to use **Django Deploy**, you must first install the following dependencies:
- [Python](https://www.python.org/downloads/) 3.5 or higher
- [virtualenv](https://virtualenv.pypa.io/en/stable/installation/)
- [Docker](https://docs.docker.com/install/overview/) (any edition)
- [Google Cloud SDK](https://cloud.google.com/sdk/docs/quickstarts)
- [kubectl](https://cloud.google.com/kubernetes-engine/docs/quickstart) (can be
  installed with `gcloud components install kubectl`)
- [Cloud SQL Proxy](https://cloud.google.com/sql/docs/mysql/connect-admin-proxy#install)

You will also need a
[Google Cloud Platform billing account](https://cloud.google.com/billing/docs/how-to/manage-billing-account).
If you don't already have one, you can
[create one](https://console.cloud.google.com/billing). If you are new to
Google Cloud Platform, you may be able to take advantage of a
[free trial](https://cloud.google.com/free/).

## Installation

```bash
$ virtualenv -p python3 django-deploy # requires Python 3.5 or higher
$ source django-deploy/bin/activate
$ pip install django-cloud-deploy
```

## Running

```bash
$ django-cloud-deploy new
```

## Steps

Follow the prompts displayed in the terminal.

During the installation process, you will be prompted, in your web browser, to
associate your Google account with the Google.

You will also be prompted, in your web browser, to associate the project
created by **Django Deploy** with a
[Google Cloud Platform billing account](https://cloud.google.com/billing/docs/how-to/modify-project#enable_billing_for_a_project).
