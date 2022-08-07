from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from accounts.models import User
from threads.models import Thread, Comment, CommentAttachment


class CommentTestCase(TestCase):
    def setUp(self):
        self.small_gif = (
            b"\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x00\x00\x00\x21\xf9\x04"
            b"\x01\x0a\x00\x01\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02"
            b"\x02\x4c\x01\x00\x3b"
        )
        self.file1 = SimpleUploadedFile(
            "small1.gif", self.small_gif, content_type="image/gif"
        )

        self.user = User.objects.create(username="test")
        self.thread = Thread.objects.create()
        self.comment1 = Comment.objects.create(
            thread=self.thread, body="line1", created_by=self.user
        )
        self.comment2 = Comment.objects.create(
            thread=self.thread, body="line2", created_by=self.user
        )
        self.attachment1 = CommentAttachment.objects.create(
            comment=self.comment1, file=self.file1
        )
        self.attachment2 = CommentAttachment.objects.create(
            comment=self.comment1, file=self.file1
        )

    def test_delete_attachment(self):
        self.assertEqual(CommentAttachment.objects.count(), 2)
        self.attachment2.delete()
        self.assertEqual(CommentAttachment.objects.count(), 1)
        self.assertIsNotNone(self.attachment2.deleted_at)

    def test_delete_comment(self):
        self.assertEqual(self.thread.comments.count(), 2)
        self.comment1.delete()
        self.assertEqual(self.thread.comments.count(), 1)
        self.assertEqual(CommentAttachment.objects.count(), 0)

        self.comment1.refresh_from_db()
        self.attachment1.refresh_from_db()
        self.attachment2.refresh_from_db()

        self.assertIsNotNone(self.comment1.deleted_at)
        self.assertIsNotNone(self.attachment1.deleted_at)
        self.assertIsNotNone(self.attachment2.deleted_at)

    def test_delete_thread(self):
        self.assertEqual(Thread.objects.count(), 1)
        self.assertEqual(Comment.objects.count(), 2)
        self.assertEqual(CommentAttachment.objects.count(), 2)
        self.thread.delete()
        self.assertEqual(CommentAttachment.objects.count(), 0)
        self.assertEqual(Comment.objects.count(), 0)
        self.assertEqual(Thread.objects.count(), 0)
