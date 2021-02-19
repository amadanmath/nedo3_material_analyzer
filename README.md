Building and initialisation
===========================

Web Server
----------

    # Make sure `app/nedo3/settings_local.py` exists and defines workers
    # (and overrides whatever needs overriding)
    # Make sure `.env` exists and is correct (copy from .env.skel)

    docker-compose up -d --build
    docker-compose exec web python manage.py collectstatic --noinput
    docker-compose exec web python manage.py createsuperuser

Worker
------
    cd sample_worker
    docker-compose up -d --build
