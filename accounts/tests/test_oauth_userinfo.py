from datetime import timedelta
import hashlib

from django.utils import timezone
from django_tenants.test.cases import TenantTestCase
from django_tenants.test.client import TenantClient
from oauth2_provider.models import (
    get_access_token_model,
    get_application_model,
    get_refresh_token_model,
)

from accounts.models import Authority, AuthorityUser


class OAuthUserInfoTests(TenantTestCase):
    @classmethod
    def setup_tenant(cls, tenant):
        tenant.name = "Tenant Alpha"

    def setUp(self):
        self.client = TenantClient(self.tenant)
        self.authority = Authority.objects.create(code="TH", name="Thailand")
        self.user = AuthorityUser.objects.create(
            username="oauth-user",
            first_name="OAuth",
            last_name="User",
            email="oauth@example.com",
            authority=self.authority,
            is_superuser=True,
        )
        self.user.set_password("oauth-pass-123")
        self.user.save(update_fields=("password",))

        application_model = get_application_model()
        self.application = application_model.objects.create(
            name="userinfo-client",
            user=self.user,
            client_type=application_model.CLIENT_CONFIDENTIAL,
            authorization_grant_type=application_model.GRANT_PASSWORD,
        )

        access_token_model = get_access_token_model()
        self.access_token = access_token_model.objects.create(
            user=self.user,
            token="oauth-userinfo-token",
            application=self.application,
            expires=timezone.now() + timedelta(hours=1),
            scope="read write",
        )

    def test_userinfo_returns_expected_payload_for_bearer_token(self):
        response = self.client.get(
            "/api/userinfo/",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token.token}",
        )

        self.assertEqual(200, response.status_code)
        self.assertEqual(
            {
                "id": self.user.id,
                "username": "Tenant Alpha_oauth-user",
                "email": "oauth@example.com",
                "first_name": "OAuth",
                "last_name": "User",
                "is_superuser": True,
                "authority": {
                    "id": self.authority.id,
                    "name": "Thailand",
                    "code": "TH",
                },
            },
            response.json(),
        )

    def test_password_grant_creates_token_family_and_checksum(self):
        application_model = get_application_model()
        app = application_model.objects.create(
            name="password-client",
            user=self.user,
            client_type=application_model.CLIENT_CONFIDENTIAL,
            authorization_grant_type=application_model.GRANT_PASSWORD,
            client_secret="plain-secret",
            hash_client_secret=False,
        )

        token_response = self.client.post(
            "/o/token/",
            data={
                "grant_type": "password",
                "username": self.user.username,
                "password": "oauth-pass-123",
                "client_id": app.client_id,
                "client_secret": "plain-secret",
                "scope": "read write",
            },
        )

        self.assertEqual(200, token_response.status_code)
        payload = token_response.json()

        access_token_model = get_access_token_model()
        refresh_token_model = get_refresh_token_model()

        access_token = access_token_model.objects.get(token=payload["access_token"])
        refresh_token = refresh_token_model.objects.get(token=payload["refresh_token"])

        self.assertEqual(
            hashlib.sha256(payload["access_token"].encode("utf-8")).hexdigest(),
            access_token.token_checksum,
        )
        self.assertIsNotNone(refresh_token.token_family)

        userinfo_response = self.client.get(
            "/api/userinfo/",
            HTTP_AUTHORIZATION=f"Bearer {payload['access_token']}",
        )

        self.assertEqual(200, userinfo_response.status_code)
        self.assertEqual("Tenant Alpha_oauth-user", userinfo_response.json()["username"])
