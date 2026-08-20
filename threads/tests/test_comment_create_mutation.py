from django.core.files.uploadedfile import SimpleUploadedFile

from threads.tests.test_base import BaseTestCase


class CommentCreateMutationTests(BaseTestCase):
    def setUp(self):
        super().setUp()
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
            item
            for item in listed.data["comments"]
            if item["id"] == payload["id"]
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
