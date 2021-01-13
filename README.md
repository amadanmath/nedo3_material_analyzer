Building and initialisation

    docker-compose -f docker-compose.yml up -d --build
    docker-compose exec web python manage.py collectstatic --noinput
    docker-compose exec web python manage.py createsuperuser
