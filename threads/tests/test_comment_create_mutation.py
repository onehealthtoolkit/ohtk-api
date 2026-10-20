import json
from io import BytesIO
from tempfile import TemporaryDirectory

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, override_settings
from graphql_jwt.shortcuts import get_token
from PIL import Image

from threads.attachment_files import MAX_ATTACHMENT_BYTES
from threads.models import Comment, CommentAttachment
from threads.tests.test_base import BaseTestCase


class CommentCreateMutationTests(BaseTestCase):
    attachment_mutation = """
        mutation commentCreate($body: String!, $threadId: Int!, $files: [Upload]) {
            commentCreate(body: $body, threadId: $threadId, files: $files) {
                result {
                    __typename
                    ... on CommentCreateSuccess {
                        id
                        body
                        attachments {
                            id filename contentType kind file thumbnail
                        }
                    }
                    ... on CommentCreateProblem {
                        fields { name message }
                    }
                }
            }
        }
    """

    def setUp(self):
        super().setUp()
        media_root = self.enterContext(TemporaryDirectory())
        self.enterContext(
            override_settings(
                MEDIA_ROOT=media_root,
                STORAGES={
                    "default": {
                        "BACKEND": "django.core.files.storage.FileSystemStorage"
                    },
                    "staticfiles": {
                        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
                    },
                },
            )
        )
        self.small_gif = (
            b"\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x00\x00\x00\x21\xf9\x04"
            b"\x01\x0a\x00\x01\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02"
            b"\x02\x4c\x01\x00\x3b"
        )
        self.file1 = SimpleUploadedFile(
            "small1.gif", self.small_gif, content_type="image/gif"
        )
        self.file2 = SimpleUploadedFile(
            "small2.gif", self.small_gif, content_type="image/gif"
        )

    def create_with_attachments(self, files):
        result = self.client.execute(
            self.attachment_mutation,
            {"body": "mobile photo", "threadId": self.thread.id, "files": files},
        )
        self.assertIsNone(result.errors, result.errors)
        return result.data["commentCreate"]["result"]

    def test_legacy_mobile_images_are_saved_and_queryable_with_thumbnails(self):
        for image_format, extension, content_type in (
            ("JPEG", ".jpg", "image/jpeg"),
            ("PNG", ".png", "image/png"),
            ("GIF", ".gif", "image/gif"),
            ("WEBP", ".webp", "image/webp"),
        ):
            with self.subTest(image_format=image_format):
                buffer = BytesIO()
                Image.new("RGB", (4, 4), color="red").save(buffer, format=image_format)
                data = buffer.getvalue()
                filename = f"mobile-uuid-{image_format.lower()}"
                upload = SimpleUploadedFile(
                    filename, data, content_type="application/octet-stream"
                )

                payload = self.create_with_attachments([upload])

                self.assertEqual(payload["__typename"], "CommentCreateSuccess")
                self.assertEqual(payload["body"], "mobile photo")
                attachment = payload["attachments"][0]
                self.assertEqual(attachment["filename"], filename + extension)
                self.assertEqual(attachment["contentType"], content_type)
                self.assertEqual(attachment["kind"], "IMAGE")
                self.assertTrue(attachment["file"])
                self.assertTrue(attachment["thumbnail"])
                saved = CommentAttachment.objects.get(pk=attachment["id"])
                with saved.file.open("rb") as stored:
                    self.assertEqual(stored.read(), data)

                listed = self.client.execute(
                    """query comments($threadId: ID!) {
                        comments(threadId: $threadId) {
                            id
                            attachments { filename contentType kind file thumbnail }
                        }
                    }""",
                    {"threadId": self.thread.id},
                )
                self.assertIsNone(listed.errors, listed.errors)
                found = next(
                    item
                    for item in listed.data["comments"]
                    if item["id"] == payload["id"]
                )
                self.assertEqual(
                    found["attachments"][0],
                    {key: value for key, value in attachment.items() if key != "id"},
                )

    def test_invalid_legacy_attachment_creates_no_comment_or_partial_attachments(self):
        for data in (b"not an image", self.small_gif + bytes(MAX_ATTACHMENT_BYTES)):
            with self.subTest(size=len(data)):
                good = SimpleUploadedFile(
                    "good-uuid", self.small_gif, content_type="application/octet-stream"
                )
                bad = SimpleUploadedFile(
                    "bad-uuid", data, content_type="application/octet-stream"
                )

                payload = self.create_with_attachments([good, bad])

                self.assertEqual(payload["__typename"], "CommentCreateProblem")
                self.assertEqual(payload["fields"][0]["name"], "files")
                self.assertEqual(Comment.objects.count(), 0)
                self.assertEqual(CommentAttachment.objects.count(), 0)

    def test_legacy_mobile_image_through_http_multipart_endpoint(self):
        http = Client(HTTP_HOST="localhost")
        upload = SimpleUploadedFile(
            "d1a1ce5c-ec9a-4998-8ecf-792cd419f7c2",
            self.small_gif,
            content_type="application/octet-stream",
        )
        response = http.post(
            "/graphql/",
            {
                "operations": json.dumps(
                    {
                        "query": self.attachment_mutation,
                        "variables": {
                            "body": "mobile photo",
                            "threadId": self.thread.id,
                            "files": [None],
                        },
                    }
                ),
                "map": json.dumps({"0": ["variables.files.0"]}),
                "0": upload,
            },
            HTTP_AUTHORIZATION=f"JWT {get_token(self.user)}",
        )

        self.assertEqual(response.status_code, 200, response.content)
        result = response.json()
        self.assertNotIn("errors", result, result)
        payload = result["data"]["commentCreate"]["result"]
        self.assertEqual(payload["__typename"], "CommentCreateSuccess")
        attachment = payload["attachments"][0]
        self.assertEqual(attachment["filename"], upload.name + ".gif")
        self.assertEqual(attachment["contentType"], "image/gif")
        self.assertEqual(attachment["kind"], "IMAGE")
        self.assertTrue(attachment["thumbnail"])
        saved = CommentAttachment.objects.get(pk=attachment["id"])
        with saved.file.open("rb") as stored:
            self.assertEqual(stored.read(), self.small_gif)

    def test_create_comment_with_body_only(self):
        mutation = """
        mutation commentCreate($body: String!, $threadId: Int!) {
            commentCreate(body: $body, threadId: $threadId) {
                result {
                    __typename
                    ... on CommentCreateSuccess {
                        id
                        body            
                        threadId
                        attachments {
                            file
                        }
                        createdBy {
                            username
                        }        
                    }
                    ... on CommentCreateProblem {
                        message
                        fields {
                            name
                            message
                        }                    
                    }                    
                }
            }
        }
        """
        result = self.client.execute(
            mutation, {"body": "test comment", "threadId": self.thread.id}
        )
        print(result)
        self.assertIsNotNone(result.data["commentCreate"])
        self.assertIsNotNone(result.data["commentCreate"]["result"]["id"])
        self.assertEqual(result.data["commentCreate"]["result"]["body"], "test comment")

    def test_create_comment_with_multiple_files(self):
        mutation = """
        mutation commentCreate($body: String!, $threadId: Int!, $files: [Upload]) {
            commentCreate(body: $body, threadId: $threadId, files: $files) {
                result {
                    __typename
                    ... on CommentCreateSuccess {
                        id
                        body            
                        threadId
                        attachments {
                            file
                        }
                        createdBy {
                            username
                        }        
                    }       
                }
            }
        }
        """
        result = self.client.execute(
            mutation,
            {
                "body": "test comment",
                "threadId": self.thread.id,
                "files": [
                    self.file1,
                    self.file2,
                ],
            },
        )
        print(result)
        self.assertIsNotNone(result.data["commentCreate"])
        self.assertIsNotNone(result.data["commentCreate"]["result"]["id"])
        self.assertEqual(result.data["commentCreate"]["result"]["body"], "test comment")
        self.assertEqual(len(result.data["commentCreate"]["result"]["attachments"]), 2)

    def test_create_comment_with_pdf_does_not_break_comments_query(self):
        pdf = SimpleUploadedFile(
            "lab-result.pdf",
            b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n",
            content_type="application/pdf",
        )
        mutation = """
        mutation commentCreate($body: String!, $threadId: Int!, $files: [Upload]) {
            commentCreate(body: $body, threadId: $threadId, files: $files) {
                result {
                    __typename
                    ... on CommentCreateSuccess {
                        id
                        attachments {
                            filename
                            kind
                            thumbnail
                            file
                        }
                    }
                    ... on CommentCreateProblem {
                        message
                        fields { name message }
                    }
                }
            }
        }
        """
        result = self.client.execute(
            mutation,
            {
                "body": "lab file",
                "threadId": self.thread.id,
                "files": [pdf],
            },
        )
        self.assertIsNone(result.errors, result.errors)
        payload = result.data["commentCreate"]["result"]
        self.assertEqual(payload["__typename"], "CommentCreateSuccess")
        attachment = payload["attachments"][0]
        self.assertEqual(attachment["filename"], "lab-result.pdf")
        self.assertEqual(attachment["kind"], "DOCUMENT")
        self.assertIsNone(attachment["thumbnail"])
        self.assertTrue(attachment["file"])

        query = """
        query comments($threadId: ID!) {
            comments(threadId: $threadId) {
                id
                attachments {
                    filename
                    kind
                    thumbnail
                }
            }
        }
        """
        listed = self.client.execute(query, {"threadId": self.thread.id})
        self.assertIsNone(listed.errors, listed.errors)
        found = next(
            item for item in listed.data["comments"] if item["id"] == payload["id"]
        )
        self.assertEqual(found["attachments"][0]["kind"], "DOCUMENT")
        self.assertIsNone(found["attachments"][0]["thumbnail"])

    def test_create_comment_rejects_disallowed_file_type(self):
        exe = SimpleUploadedFile(
            "malware.exe",
            b"MZ",
            content_type="application/octet-stream",
        )
        mutation = """
        mutation commentCreate($body: String!, $threadId: Int!, $files: [Upload]) {
            commentCreate(body: $body, threadId: $threadId, files: $files) {
                result {
                    __typename
                    ... on CommentCreateProblem {
                        fields { name message }
                    }
                }
            }
        }
        """
        result = self.client.execute(
            mutation,
            {
                "body": "nope",
                "threadId": self.thread.id,
                "files": [exe],
            },
        )
        self.assertIsNone(result.errors, result.errors)
        fields = result.data["commentCreate"]["result"]["fields"]
        self.assertEqual(fields[0]["name"], "files")
        self.assertIn("PDF", fields[0]["message"])
