from datetime import timedelta

from django.utils import timezone
from graphql_jwt.testcases import JSONWebTokenClient

from threads.models import Comment, Thread
from threads.tests.test_base import BaseTestCase


class CommentQueryTestCase(BaseTestCase):
    client_class = JSONWebTokenClient

    def setUp(self):
        super().setUp()
        self.comment1 = Comment.objects.create(
            created_by=self.user, thread=self.thread, body="test comment1"
        )
        self.comment2 = Comment.objects.create(
            created_by=self.user, thread=self.thread, body="test comment2"
        )
        self.comment3 = Comment.objects.create(
            created_by=self.user, thread=self.thread, body="test comment3"
        )
        self.created_at = timezone.now()
        # Creation time intentionally differs from ID order.
        Comment.objects.filter(pk=self.comment1.pk).update(
            created_at=self.created_at - timedelta(minutes=1)
        )
        Comment.objects.filter(pk=self.comment2.pk).update(
            created_at=self.created_at - timedelta(minutes=2)
        )
        Comment.objects.filter(pk=self.comment3.pk).update(
            created_at=self.created_at
        )

    def query_comment_ids(self):
        query = """
        query comments($threadId: ID!) {
            comments(threadId: $threadId) {
                id
                body
                threadId
                attachments {
                    file
                }
            }
        }
        """
        result = self.client.execute(query, {"threadId": self.thread.id})
        self.assertIsNone(result.errors)
        return [comment["id"] for comment in result.data["comments"]]

    def test_query_orders_comments_newest_first(self):
        self.assertEqual(
            self.query_comment_ids(),
            [str(self.comment3.id), str(self.comment1.id), str(self.comment2.id)],
        )

    def test_query_orders_equal_timestamps_by_descending_id(self):
        Comment.objects.filter(thread=self.thread).update(created_at=self.created_at)

        self.assertEqual(
            self.query_comment_ids(),
            [str(self.comment3.id), str(self.comment2.id), str(self.comment1.id)],
        )

    def test_query_excludes_other_threads_and_deleted_comments(self):
        Comment.objects.create(
            created_by=self.user, thread=Thread.objects.create(), body="other thread"
        )
        deleted_comment = Comment.objects.create(
            created_by=self.user, thread=self.thread, body="deleted comment"
        )
        deleted_comment.delete()

        self.assertEqual(
            self.query_comment_ids(),
            [str(self.comment3.id), str(self.comment1.id), str(self.comment2.id)],
        )
