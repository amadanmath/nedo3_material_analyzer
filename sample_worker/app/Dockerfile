###########
# BUILDER #
###########

# pull official base image
FROM python:3.7-slim-stretch as builder

# set work directory
WORKDIR /usr/src/app

# set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

RUN apt update \
    && apt install -y build-essential python3-dev

COPY ./requirements.txt .
RUN pip3 install --upgrade pip wheel \
    && pip3 wheel --no-cache-dir --no-deps --wheel-dir /usr/src/app/wheels -r requirements.txt


#########
# FINAL #
#########

# pull official base image
FROM python:3.7-slim-stretch

ENV HOME=/home/app APP_HOME=/home/app/web

# create directory for the app user
RUN mkdir -p $HOME $APP_HOME \
    && addgroup --system app \
    && adduser --system --ingroup app app \
    && chown app:app $HOME $APP_HOME
    # && apt-get update \
    # && apt-get install -y build-essential

WORKDIR $APP_HOME

# install dependencies
COPY --chown=app:app --from=builder /usr/src/app/wheels /wheels
RUN pip install --no-cache-dir /wheels/*

# copy project
COPY --chown=app:app . $APP_HOME

# change to the app user
USER app

# run entrypoint.sh
ENTRYPOINT ["/home/app/web/entrypoint.sh"]
