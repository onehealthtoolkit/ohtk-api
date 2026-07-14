from django.conf import settings
from django.core.files.storage import FileSystemStorage
from storages.backends.s3boto3 import S3Boto3Storage


class S3MediaStorage(S3Boto3Storage):
    """
    Media files on S3 or S3-compatible storage (e.g. MinIO).

    Endpoint, path-style addressing, and custom domain come from Django settings
    (AWS_S3_ENDPOINT_URL, AWS_S3_ADDRESSING_STYLE, AWS_S3_CUSTOM_DOMAIN, etc.).
    """

    location = "media"

    def __init__(self, **kwargs):
        kwargs.setdefault(
            "bucket_name",
            getattr(settings, "AWS_STORAGE_BUCKET_NAME", None),
        )
        endpoint = getattr(settings, "AWS_S3_ENDPOINT_URL", None)
        if endpoint and "endpoint_url" not in kwargs:
            kwargs["endpoint_url"] = endpoint
        addressing = getattr(settings, "AWS_S3_ADDRESSING_STYLE", None)
        if addressing and "addressing_style" not in kwargs:
            kwargs["addressing_style"] = addressing
        custom_domain = getattr(settings, "AWS_S3_CUSTOM_DOMAIN", None)
        if custom_domain and "custom_domain" not in kwargs:
            kwargs["custom_domain"] = custom_domain
        if (
            hasattr(settings, "AWS_S3_USE_SSL")
            and "use_ssl" not in kwargs
        ):
            kwargs["use_ssl"] = settings.AWS_S3_USE_SSL
        if (
            hasattr(settings, "AWS_DEFAULT_ACL")
            and "default_acl" not in kwargs
        ):
            kwargs["default_acl"] = settings.AWS_DEFAULT_ACL
        super().__init__(**kwargs)


class SimpleFileMediaStorage(FileSystemStorage):
    def url(self, name):
        return f"https://{settings.MEDIA_DOMAIN}{settings.MEDIA_URL}{name}"
