# Django Deploy

**Django Deploy** is an experimental tool designed to make it easier to
deploy new and existing [Django](https://www.djangoproject.com/) applications
on public clouds
(e.g. [Kubernetes Engine](https://cloud.google.com/kubernetes-engine/)).

Currently, **Django Deploy** can only
- Deploy to [Google App Engine](https://cloud.google.com/appengine/).
- Deploy to [Kubernetes Engine](https://cloud.google.com/kubernetes-engine/).
- Deploy applications created using its own template code.

**Django Deploy** is an experimental project not officially supported by Google.

Here is an example usage:

<pre>
$ django-cloud-deploy new
<b>11 steps to setup your new project</b>

[<b>1/11</b>] In order to deploy your application, you must allow Django Deploy to access your Google account.
Press [Enter] to open a browser window to allow access
[<b>2/11</b>] Enter a Google Cloud Platform Project ID, or leave blank to use
[django-799931]: my-cool-site 
[<b>3/11</b>] Enter a Google Cloud Platform project name, or leave blank to use
[Django Project]: My Cool Site
[<b>4/11</b>] In order to deploy your application, you must enable billing for your Google Cloud Project.
You have the following existing billing accounts: 
1. My Billing Account
Please enter your numeric choice or press [Enter] to create a new billing account: 1
[<b>5/11</b>] Enter a password for the default database user "postgres"
Password: 
Password (again): 
[<b>6/11</b>] Enter a new directory path to store project source, or leave blank to use
[/usr/local/google/home/bquinlan/my-cool-site]: 
[<b>7/11</b>] Enter a Django project name, or leave blank to use
[mysite]: mycoolsite
[<b>8/11</b>] Enter a Django app name, or leave blank to use
[home]: mycoolapp
[<b>9/11</b>] Enter a name for the Django superuser, or leave blank to use
[admin]: myname
[<b>10/11</b>] Enter a password for the Django superuser "myname"
Password: 
Password (again): 
[<b>11/11</b>] Enter a e-mail address for the Django superuser, or leave blank to use
[test@example.com]: myname@example.com
</pre>

# Getting Started

For detailed instructions on how to use **Django Deploy**, see the
[Getting Started Guide](https://github.com/GoogleCloudPlatform/django-cloud-deploy/blob/master/GETTING-STARTED.md).

# Development Workflow (Linux)

Verify that Python 3.5 or later is installed:

```bash
python3 -V
```

Clone the project and cd to it's directory:

```bash
git clone https://github.com/GoogleCloudPlatform/django-cloud-deploy
cd django-cloud-deploy
```

Create a new virtual environment:
```bash
virtualenv -p python3 venv
source venv/bin/activate
```

Install **Django Deploy** in edit mode:
```bash
pip install -e .
```

Run it:
```bash
django-cloud-deploy new
```

Code modifications will be reflected in the next run of `django-cloud-deploy`.

## Contribute

Check out our [CONTRIBUTING](https://github.com/GoogleCloudPlatform/django-cloud-deploy/blob/master/CONTRIBUTING.md) to find out how you can help.

## License

This project is licensed under the Apache License - see the [LICENSE](https://github.com/GoogleCloudPlatform/django-cloud-deploy/blob/master/LICENSE) file for details

This is not an officially supported Google product.

## Status

**Django Deploy** is an experimental project not officially supported by Google.
