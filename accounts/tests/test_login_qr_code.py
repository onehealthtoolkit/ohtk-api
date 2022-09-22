from django.test import TestCase
from graphql_jwt.testcases import JSONWebTokenClient, JSONWebTokenTestCase

from accounts.models import AuthorityUser, Authority
from tenants.models import Client


class MockTenantClient(JSONWebTokenClient):
    def request(self, **request):
        request = super().request(**request)
        tenant = Client()
        tenant.domain_url = "opensur.test"
        request.tenant = tenant
        return request


class LoginQRCodeTestCase(TestCase):
    client_class = MockTenantClient

    def setUp(self):
        self.authority = Authority.objects.create(
            code="A1",
            name="A1 name",
        )
        self.reporter = AuthorityUser.objects.create(
            username="testuser",
            authority=self.authority,
            role=AuthorityUser.Role.REPORTER,
        )
        self.admin_user = AuthorityUser.objects.create(
            username="adminuser",
            authority=self.authority,
            role=AuthorityUser.Role.ADMIN,
        )
        self.client.authenticate(self.admin_user)

    def test_get_login_qr_token(self):
        response = self.client.execute(
            """
            query getLoginQrToken($userId: ID!) {
                getLoginQrToken(userId: $userId) {
                    token
                }
            }
            """,
            variables={"userId": self.reporter.id},
        )
        self.assertIsNotNone(response.data["getLoginQrToken"]["token"])
        token = response.data["getLoginQrToken"]["token"]

        response = self.client.execute(
            """
            mutation verifyLoginQrToken($token: String!) {
                verifyLoginQrToken(token: $token) {
                    me {
                        id
                    }
                    token
                }
            }        
            """,
            variables={"token": token},
        )
        self.assertIsNone(response.errors)
        self.assertIsNotNone(response.data["verifyLoginQrToken"]["me"])
