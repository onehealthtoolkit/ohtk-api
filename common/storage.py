from django.core.files.storage import FileSystemStorage
from storages.backends.s3boto3 import S3Boto3Storage

from podd_api import settings


class S3MediaStorage(S3Boto3Storage):
    bucket_name = settings.MEDIA_BUCKET_NAME
    location = "media"


class SimpleFileMediaStorage(FileSystemStorage):
    def url(self, name):
        return f"https://opensur.test{settings.MEDIA_URL}{name}"
