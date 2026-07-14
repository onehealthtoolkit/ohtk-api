from django.test import SimpleTestCase, override_settings

from common.storage import S3MediaStorage


@override_settings(
    AWS_STORAGE_BUCKET_NAME="lahis-media",
    AWS_ACCESS_KEY_ID="test-access",
    AWS_SECRET_ACCESS_KEY="test-secret",
    AWS_S3_REGION_NAME="us-east-1",
    AWS_S3_ENDPOINT_URL="http://minio:9000",
    AWS_S3_ADDRESSING_STYLE="path",
    AWS_S3_CUSTOM_DOMAIN="minio.lahis.ohtk.org",
    AWS_S3_USE_SSL=False,
    AWS_DEFAULT_ACL=None,
    AWS_S3_SIGNATURE_VERSION="s3v4",
)
class S3MediaStorageMinIOConfigTests(SimpleTestCase):
    """Config smoke: S3MediaStorage honors MinIO-oriented settings."""

    def test_endpoint_path_style_and_custom_domain(self):
        storage = S3MediaStorage()
        self.assertEqual(storage.bucket_name, "lahis-media")
        self.assertEqual(storage.endpoint_url, "http://minio:9000")
        self.assertEqual(storage.addressing_style, "path")
        self.assertEqual(storage.custom_domain, "minio.lahis.ohtk.org")
        self.assertFalse(storage.use_ssl)
        self.assertIsNone(storage.default_acl)
        self.assertEqual(storage.location, "media")

    def test_public_url_uses_custom_domain_prefix(self):
        storage = S3MediaStorage()
        url = storage.url("reports/example.jpg")
        # custom_domain URLs should not point at minio:9000
        self.assertIn("minio.lahis.ohtk.org", url)
        self.assertNotIn("minio:9000", url)
        self.assertIn("media", url)
