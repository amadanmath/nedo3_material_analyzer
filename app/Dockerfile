###########
# BUILDER #
###########

# pull official base image
FROM python:3.8.3-alpine as builder

# set work directory
WORKDIR /usr/src/app

# set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

# install psycopg2 dependencies
# libffi-dev apparently needed on OSX
RUN apk update \
    && apk add libffi-dev postgresql-dev gcc g++ python3-dev musl-dev

COPY ./requirements.txt .
RUN pip install --upgrade pip \
    && pip wheel --no-cache-dir --no-deps --wheel-dir /usr/src/app/wheels -r requirements.txt



#########
# FINAL #
#########

# pull official base image
FROM python:3.8.3-alpine

ENV HOME=/home/app APP_HOME=/home/app/web

# create directory for the app user
RUN mkdir -p $HOME $APP_HOME $APP_HOME/static \
    && addgroup -S app \
    && adduser -S app -G app

WORKDIR $APP_HOME

# install dependencies
COPY --chown=app:app --from=builder /usr/src/app/wheels /wheels
COPY --chown=app:app --from=builder /usr/src/app/requirements.txt .
COPY --chown=app:app --from=builder /usr/lib/libstdc++.so.6 /usr/lib/libgcc_s.so.1 /usr/lib/
RUN apk update \
    && apk add libpq \
    && pip install --no-cache /wheels/* \
    && sudachipy link -t core

# copy project
COPY --chown=app:app . $APP_HOME

# change to the app user
USER app

# run entrypoint.sh
ENTRYPOINT ["/home/app/web/entrypoint.sh"]
