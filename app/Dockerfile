###########
# BUILDER #
###########

# pull official base image
FROM python:3.7-slim-stretch as builder

# set work directory
WORKDIR /usr/src/app

# set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

# install psycopg2 dependencies
# libffi-dev apparently needed on OSX
# RUN apk update \
#     && apk add py-pip py-cryptography libffi-dev postgresql-dev gcc g++ python3-dev musl-dev
RUN apt-get update \
    && apt-get install -y build-essential python3-dev libpq-dev


COPY ./bare_requirements.txt .
RUN pip3 install --upgrade pip wheel \
    && pip3 wheel --no-cache-dir --no-deps --wheel-dir /usr/src/app/wheels -r bare_requirements.txt



#########
# FINAL #
#########

# pull official base image
FROM python:3.7-slim-stretch

ENV HOME=/home/app APP_HOME=/home/app/web

# create directory for the app user
RUN mkdir -p $HOME $APP_HOME $APP_HOME/static \
    && addgroup --system app \
    && adduser --system --ingroup app app \
    && chown app:app $HOME $APP_HOME $APP_HOME/static \
    && apt-get update \
    && apt-get install -y build-essential libpq-dev

WORKDIR $APP_HOME

# install dependencies
COPY --chown=app:app --from=builder /usr/src/app/wheels /wheels
RUN apt-get update \
    && apt-get install -y gcc netcat \
    && pip3 install --no-cache /wheels/* \
    && sudachipy link -t core

# copy project
COPY --chown=app:app . $APP_HOME

# change to the app user
USER app

# run entrypoint.sh
ENTRYPOINT ["/home/app/web/entrypoint.sh"]
