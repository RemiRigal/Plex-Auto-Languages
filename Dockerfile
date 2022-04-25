FROM python:3.8-alpine

ENV LANG C.UTF-8
ENV LC_ALL C.UTF-8

COPY ./requirements.txt /app/requirements.txt

RUN python3 -m pip install --no-cache-dir -r /app/requirements.txt

COPY . /app/

WORKDIR /app

VOLUME /config

ENTRYPOINT ["python3", "main.py", "-c", "/config/config.yaml"]
