from graphql_jwt.testcases import JSONWebTokenTestCase
from django.test.utils import override_settings
from accounts.models import User, PasswordResetToken


class PasswordResetTests(JSONWebTokenTestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="test@bon.co.th"
        )

    @override_settings(DEBUG=True)
    def test_reset_password_request(self):
        query = """
        mutation resetPasswordRequest($email: String!) {
            resetPasswordRequest(email: $email) {
                success
            }
        }
        """
        result = self.client.execute(query, variables={"email": "test@bon.co.th"})
        self.assertTrue(result.data["resetPasswordRequest"]["success"])
        prt = PasswordResetToken.objects.get(user=self.user)
        self.assertIsNotNone(prt)

    @override_settings(DEBUG=True)
    def test_reset_password(self):
        query = """
            mutation resetPasswordRequest($email: String!) {
                resetPasswordRequest(email: $email) {
                    success
                }
            }
            """
        result = self.client.execute(query, variables={"email": "test@bon.co.th"})
        prt = PasswordResetToken.objects.get(user=self.user)
        query = """
                    mutation resetPassword($token: String!, $password: String!) {
                        resetPassword(token: $token, password: $password) {
                            success
                        }
                    }
                    """
        result = self.client.execute(
            query, variables={"token": prt.token, "password": "newpassword"}
        )
        prt.refresh_from_db()
        self.assertIsNotNone(prt.deleted_at)
