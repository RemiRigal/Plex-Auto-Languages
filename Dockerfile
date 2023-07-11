FROM python:3.8-alpine

ENV LANG C.UTF-8
ENV LC_ALL C.UTF-8
ENV CONTAINERIZED True

RUN apk add --update curl tini && \
    rm -rf /var/cache/apk/*

COPY ./requirements.txt /app/requirements.txt

RUN python3 -m pip install --no-cache-dir -r /app/requirements.txt

COPY . /app/

WORKDIR /app

VOLUME /config

HEALTHCHECK CMD curl --silent --fail http://localhost:9880/ || exit 1

ENTRYPOINT ["/sbin/tini", "-s", "python3", "main.py", "-c", "/config/config.yaml"]
