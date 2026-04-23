from django.contrib.auth import get_user_model
from django_tenants.utils import tenant_context
from graphql_jwt.testcases import JSONWebTokenTestCase

from tenants.models import Client


class TenantMutationTests(JSONWebTokenTestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            username="root-admin",
            password="s3cret-pass",
        )
        self.client.authenticate(self.admin)

    def test_admin_client_create_bootstraps_tenant_schema(self):
        result = self.client.execute(
            """
            mutation CreateClient($name: String!, $schemaName: String!) {
                adminClientCreate(name: $name, schemaName: $schemaName) {
                    result {
                        __typename
                        ... on AdminClientCreateSuccess {
                            id
                            name
                            schemaName
                        }
                    }
                }
            }
            """,
            variables={
                "name": "Tenant Alpha",
                "schemaName": "tenant_alpha",
            },
        )

        self.assertIsNone(result.errors)
        payload = result.data["adminClientCreate"]["result"]
        self.assertEqual("AdminClientCreateSuccess", payload["__typename"])
        self.assertEqual("Tenant Alpha", payload["name"])
        self.assertEqual("tenant_alpha", payload["schemaName"])

        tenant = Client.objects.get(schema_name="tenant_alpha")
        with tenant_context(tenant):
            self.assertTrue(
                get_user_model()
                .objects.filter(username="admin", is_superuser=True)
                .exists()
            )
