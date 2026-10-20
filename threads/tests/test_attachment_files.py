from io import BytesIO
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile, TemporaryUploadedFile
from django.test import SimpleTestCase
from PIL import Image

from threads.attachment_files import MAX_ATTACHMENT_BYTES, prepare_comment_upload


class PrepareCommentUploadTests(SimpleTestCase):
    def image_bytes(self, image_format):
        buffer = BytesIO()
        Image.new("RGB", (4, 4), color="red").save(buffer, format=image_format)
        return buffer.getvalue()

    def test_legacy_images_get_matching_metadata_and_keep_their_bytes(self):
        for image_format, extension, content_type in (
            ("JPEG", ".jpg", "image/jpeg"),
            ("PNG", ".png", "image/png"),
            ("GIF", ".gif", "image/gif"),
            ("WEBP", ".webp", "image/webp"),
        ):
            with self.subTest(image_format=image_format):
                data = self.image_bytes(image_format)
                upload = SimpleUploadedFile(
                    "mobile-uuid", data, content_type="application/octet-stream"
                )
                upload.seek(3)

                self.assertIsNone(prepare_comment_upload(upload))

                self.assertEqual(upload.name, f"mobile-uuid{extension}")
                self.assertEqual(upload.content_type, content_type)
                self.assertEqual(upload.tell(), 3)
                upload.seek(0)
                self.assertEqual(upload.read(), data)

    def test_image_with_missing_content_type_is_accepted(self):
        upload = SimpleUploadedFile(
            "mobile-uuid", self.image_bytes("PNG"), content_type=""
        )
        self.assertIsNone(prepare_comment_upload(upload))
        self.assertEqual(upload.name, "mobile-uuid.png")
        self.assertEqual(upload.content_type, "image/png")

    def test_temporary_upload_remains_open_and_readable(self):
        data = self.image_bytes("PNG")
        with TemporaryUploadedFile(
            "mobile-uuid", "application/octet-stream", len(data), None
        ) as upload:
            upload.write(data)
            upload.seek(0)

            self.assertIsNone(prepare_comment_upload(upload))

            self.assertEqual(upload.name, "mobile-uuid.png")
            self.assertEqual(upload.read(), data)

    def test_invalid_or_unsupported_legacy_files_are_rejected(self):
        for data in (
            b"not an image",
            b"%PDF-1.4\n%%EOF\n",
            self.image_bytes("BMP"),
            self.image_bytes("PNG")[:24],
            self.image_bytes("JPEG")[:-20],
        ):
            with self.subTest(data=data[:12]):
                upload = SimpleUploadedFile(
                    "mobile-uuid", data, content_type="application/octet-stream"
                )
                problem = prepare_comment_upload(upload)
                self.assertEqual(problem.name, "files")
                self.assertEqual(upload.name, "mobile-uuid")
                self.assertEqual(upload.content_type, "application/octet-stream")
                self.assertEqual(upload.tell(), 0)

    def test_disallowed_extension_cannot_use_image_fallback(self):
        upload = SimpleUploadedFile(
            "image.exe",
            self.image_bytes("PNG"),
            content_type="application/octet-stream",
        )
        self.assertIsNotNone(prepare_comment_upload(upload))
        self.assertEqual(upload.name, "image.exe")

    def test_non_generic_content_type_cannot_use_image_fallback(self):
        upload = SimpleUploadedFile(
            "mobile-uuid", self.image_bytes("PNG"), content_type="text/plain"
        )
        self.assertIsNotNone(prepare_comment_upload(upload))

    def test_oversized_legacy_image_is_rejected(self):
        data = self.image_bytes("PNG")
        upload = SimpleUploadedFile(
            "mobile-uuid",
            data + bytes(MAX_ATTACHMENT_BYTES + 1 - len(data)),
            content_type="application/octet-stream",
        )
        problem = prepare_comment_upload(upload)
        self.assertIn("10 MB", problem.message)
        self.assertEqual(upload.name, "mobile-uuid")
        self.assertEqual(upload.tell(), 0)

    def test_image_exceeding_pillow_pixel_limit_is_rejected(self):
        upload = SimpleUploadedFile(
            "mobile-uuid",
            self.image_bytes("PNG"),
            content_type="application/octet-stream",
        )
        with patch.object(Image, "MAX_IMAGE_PIXELS", 10):
            self.assertIsNotNone(prepare_comment_upload(upload))
        self.assertEqual(upload.tell(), 0)

    def test_missing_upload_is_rejected(self):
        self.assertIsNotNone(prepare_comment_upload(None))
