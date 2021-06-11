#!/bin/sh

if [ "$DATABASE" = "postgres" ]
then
    echo "Waiting for postgres..."

    while ! nc -z $SQL_HOST $SQL_PORT; do
      sleep 0.1
    done

    echo "PostgreSQL started"
fi

# python manage.py flush --no-input
python manage.py migrate
python manage.py collectstatic --no-input
# DJANGO_SUPERUSER_PASSWORD=e python manage.py createsuperuser --no-input --username e --email "e@example.com"

exec "$@"
