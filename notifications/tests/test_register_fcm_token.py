from django.test import TestCase
from graphql_jwt.testcases import JSONWebTokenClient

from accounts.models import User


class RegisterFcmTokenTestCase(TestCase):
    client_class = JSONWebTokenClient

    def setUp(self) -> None:
        self.user = User.objects.create(username="test")
        self.client.authenticate(self.user)

    def test_submit_fcm_token(self):
        mutation = """
            mutation registerFcm($userId: String!, $token: String!) {
                registerFcmToken(userId: $userId, token: $token) {
                    success
                }
            }        
        """
        result = self.client.execute(
            mutation, {"userId": str(self.user.id), "token": "test_token"}
        )
        print(result)
        self.assertTrue(result.data["registerFcmToken"]["success"])
        self.user.refresh_from_db()
        self.assertEqual("test_token", self.user.fcm_token)
