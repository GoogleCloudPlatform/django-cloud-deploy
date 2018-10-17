<head>
  <base href="https://github.com/GoogleCloudPlatform/django-cloud-deploy/blob/master/"
  target="_blank">
</head>

# Django Deploy

**Django Deploy** is an experimental tool designed to make it easier to
deploy new and existing [Django](https://www.djangoproject.com/) applications
on public clouds
(e.g. [Kubernetes Engine](https://cloud.google.com/kubernetes-engine/)).

Currently, **Django Deploy** can only
- Deploy to [Kubernetes Engine](https://cloud.google.com/kubernetes-engine/).
- Deploy applications created using its own template code.

**Django Deploy** is an experimental project not official supported by Google.

# Usage

For detailed instructions see [USAGE](USAGE.md).

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

Install Django-GKE in edit mode:
```bash
pipenv  install -e .
```

Run it:
```bash
django-cloud-deploy new
```

Code modifications will be reflected in the next run of `django-cloud-deploy`.

## Contribute

Check out our [CONTRIBUTING](CONTRIBUTING.md) to find out how you can help.

## License

This project is licensed under the Apache License - see the [LICENSE](LICENSE) file for details

This is not an officially supported Google product.

## Status

**Django Deploy** is an experimental project not official supported by Google.
