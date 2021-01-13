```bash
# clone the repository
git clone <URL> <dir>

# enter the directory
cd <dir>

# make virtual environment
python3 -m venv venv

# activate it
. venv/bin/activate

# install packages
pip install -r requirements.txt

# override settings if needed
vim nedo3/settings_local.py

# migrate the database
./manage.py migrate

# create the admin user
./manage.py createsuperuser --username=<username> --email=<email>

# collect static assets
./manage.py collectstatic

# test it out
./manage.py runserver

# deploy on a WSGI container
# https://docs.djangoproject.com/en/3.1/howto/deployment/wsgi/modwsgi/
``
