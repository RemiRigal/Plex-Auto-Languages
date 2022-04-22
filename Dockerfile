FROM python:3.8-alpine
# Build with
#    docker image build --network host -t remirigal/plexautolanguages:v1.0 .
# Save with
#    docker save -o plexautolanguages_v1.0.tar remirigal/plexautolanguages:v1.0

ENV LANG C.UTF-8
ENV LC_ALL C.UTF-8

COPY ./requirements.txt /app/requirements.txt

# RUN apk add --no-cache libxslt libxml2 && \
#     apk add --no-cache --virtual .build-deps git gcc musl-dev libxslt-dev libxml2-dev py3-greenlet libressl-dev libffi-dev cargo build-base && \
#     python3 -m pip install --no-cache-dir -r /app/requirements.txt && \
#     apk del .build-deps
RUN python3 -m pip install --no-cache-dir -r /app/requirements.txt

COPY . /app/

WORKDIR /app

VOLUME /config

CMD ["python3", "main.py", "-c", "/config/config.yaml"]
