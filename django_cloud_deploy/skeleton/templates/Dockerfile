# [START docker]

# The Google App Engine python runtime is Debian Jessie with Python installed
# and various os-level packages to allow installation of popular Python
# libraries. The source is on github at:
# https://github.com/GoogleCloudPlatform/python-docker
FROM gcr.io/google_appengine/python

# Create a virtualenv for the application dependencies.
RUN virtualenv -p python3 /env
ENV PATH /env/bin:$PATH
ENV DJANGO_SETTINGS_MODULE {{ project_name }}.remote_settings

ADD requirements.txt /app/requirements.txt
RUN /env/bin/pip install -r /app/requirements.txt
ADD . /app

CMD gunicorn -b :$PORT --access-logfile - --error-logfile - {{ project_name }}.wsgi
# [END docker]
