from django.test import TestCase
from graphql_jwt.testcases import JSONWebTokenClient

from threads.models import Comment
from threads.tests.test_base import BaseTestCase


class CommentQueryTestCase(BaseTestCase):
    client_class = JSONWebTokenClient

    def setUp(self):
        super().setUp()
        self.comment1 = Comment.objects.create(
            created_by=self.user, thread=self.thread, body="test comment1"
        )
        self.comment2 = Comment.objects.create(
            created_by=self.user, thread=self.thread, body="test comment1"
        )

    def test_query(self):
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
        print(result)
        self.assertIsNotNone(result.data["comments"])
