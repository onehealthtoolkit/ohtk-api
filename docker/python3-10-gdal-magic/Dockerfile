ARG PYTHON_GDAL_IMAGE=public.ecr.aws/g0x0v6d0/python-gdal@sha256:d107493e338183633a1c74f8e01d370676e2bf57526aeb00f74425eddbd3e044
FROM ${PYTHON_GDAL_IMAGE}

RUN \
  apt-get install -y --no-install-recommends \
  libmagic1
