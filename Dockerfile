# base image
FROM docker-python-gdal

ARG SOURCE_DIR=/usr/local/src/python-gdal

RUN apt-get update && apt-get install -y git

# DB vars
ENV DB_USER ${DB_USER}
ENV DB_NAME ${DB_NAME}
ENV DB_HOST ${DB_HOST}
ENV DB_PORT ${DB_PORT}
ENV DB_PASSWORD ${DB_PASSWORD}

ENV DJANGO_SECRET_KEY ${DJANGO_SECRET_KEY}
ENV DJANGO_DEBUG ${DJANGO_DEBUG}

ENV DockerHome /usr/src/app

RUN mkdir -p $DockerHome

WORKDIR $DockerHome

ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1

ARG CPLUS_INCLUDE_PATH=/usr/include/gdal
ARG C_INCLUDE_PATH=/usr/include/gdal

COPY . $DockerHome
RUN python3 -m pip install --upgrade pip --no-cache-dir \
    && python3 -m pip install GDAL --no-cache-dir \
    && python3 -m pip install -r requirements.txt --no-cache-dir

EXPOSE 8000

ENTRYPOINT ["/usr/src/app/docker-entrypoint.sh"]
