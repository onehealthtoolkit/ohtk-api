from django.db import connection
from django.test import RequestFactory
from django_tenants.test.cases import TenantTestCase
from django_tenants.test.client import TenantClient
from oauth2_provider.models import get_access_token_model, get_application_model

from accounts.models import Authority, AuthorityUser, Configuration, User
from accounts.village_capability import FEATURE_ENABLED_VALUE
from integrations.constants import IntegrationEventType, IntegrationScope
from integrations.models import IntegrationClient, WebhookEndpoint
from integrations.policy import (
    AI_DEFAULT_COMMENT_OWNER_USER_ID_KEY,
    AI_ENABLED_KEY,
    CLUSTER_DETECTOR_ENABLED_KEY,
    DASHBOARD_RISK_WINDOW_DAYS_KEY,
    INTEGRATION_ENABLED_KEY,
    RISK_EVALUATOR_ENABLED_KEY,
)
from podd_api.schema import schema


class AdminIntegrationGraphqlTests(TenantTestCase):
    @classmethod
    def setup_tenant(cls, tenant):
        tenant.name = "Tenant Alpha"

    def setUp(self):
        connection.set_tenant(self.tenant)
        self.client = TenantClient(self.tenant)
        self.request_factory = RequestFactory()
        self.super_user = User.objects.create(
            username="platform",
            is_superuser=True,
        )
        self.normal_user = User.objects.create(username="operator")
        self.authority = Authority.objects.create(code="BKK", name="Bangkok")
        self.admin_owner = AuthorityUser.objects.create(
            username="tenant-admin",
            first_name="Tenant",
            last_name="Admin",
            authority=self.authority,
            role=AuthorityUser.Role.ADMIN,
        )

    def execute(self, query, variables=None, user=None):
        request = self.request_factory.post("/graphql/")
        request.user = user or self.super_user
        return schema.execute(query, variable_values=variables or {}, context_value=request)

    def create_client(self, code="ai-client"):
        application_model = get_application_model()
        application = application_model.objects.create(
            name=code,
            user=None,
            client_type=application_model.CLIENT_CONFIDENTIAL,
            authorization_grant_type=application_model.GRANT_CLIENT_CREDENTIALS,
        )
        return IntegrationClient.objects.create(
            name=code,
            code=code,
            integration_type=IntegrationClient.IntegrationType.AI_ASSISTANT,
            oauth_application=application,
            scope_codes=[IntegrationScope.AI_READ_REPORT],
        )

    def test_superuser_can_create_rotate_and_disable_integration_client(self):
        mutation = """
        mutation createClient($input: AdminIntegrationClientInput!) {
            adminIntegrationClientCreate(input: $input) {
                result {
                    __typename
                    ... on AdminIntegrationClientCreateSuccess {
                        clientSecret
                        integrationClient {
                            id
                            name
                            code
                            integrationType
                            status
                            clientId
                            scopeCodes
                        }
                    }
                    ... on AdminIntegrationClientCreateProblem {
                        fields { name message }
                    }
                }
            }
        }
        """
        result = self.execute(
            mutation,
            {
                "input": {
                    "name": "AI Assistant",
                    "code": "ai-assistant",
                    "integrationType": "AI_ASSISTANT",
                    "scopeCodes": [
                        IntegrationScope.AI_READ_REPORT,
                        IntegrationScope.AI_CREATE_COMMENT,
                    ],
                    "allowedCallbackDomains": ["external.example.test"],
                    "rateLimitPolicy": {"perMinute": 60},
                }
            },
        )

        self.assertIsNone(result.errors, result.errors)
        payload = result.data["adminIntegrationClientCreate"]["result"]
        self.assertEqual("AdminIntegrationClientCreateSuccess", payload["__typename"])
        self.assertTrue(payload["clientSecret"])
        self.assertEqual(
            [IntegrationScope.AI_READ_REPORT, IntegrationScope.AI_CREATE_COMMENT],
            payload["integrationClient"]["scopeCodes"],
        )
        integration_client = IntegrationClient.objects.get(code="ai-assistant")
        self.assertIsNone(integration_client.oauth_application.user)
        self.assertEqual(
            get_application_model().CLIENT_CONFIDENTIAL,
            integration_client.oauth_application.client_type,
        )
        self.assertEqual(
            get_application_model().GRANT_CLIENT_CREDENTIALS,
            integration_client.oauth_application.authorization_grant_type,
        )

        query = """
        query getClient($id: ID!) {
            adminIntegrationClientGet(id: $id) {
                id
                code
                clientId
                scopeCodes
            }
        }
        """
        get_result = self.execute(query, {"id": integration_client.id})
        self.assertIsNone(get_result.errors, get_result.errors)
        self.assertNotIn("clientSecret", get_result.data["adminIntegrationClientGet"])
        self.assertEqual(
            payload["integrationClient"]["clientId"],
            get_result.data["adminIntegrationClientGet"]["clientId"],
        )
        token_response = self.client.post(
            "/o/token/",
            data={
                "grant_type": "client_credentials",
                "client_id": payload["integrationClient"]["clientId"],
                "client_secret": payload["clientSecret"],
            },
        )
        self.assertEqual(200, token_response.status_code, token_response.content)
        token_payload = token_response.json()
        access_token = get_access_token_model().objects.get(
            token=token_payload["access_token"]
        )
        self.assertIsNone(access_token.user)
        self.assertEqual(integration_client.oauth_application, access_token.application)

        rotate = """
        mutation rotateClientSecret($id: ID!) {
            adminIntegrationClientRotateSecret(id: $id) {
                result {
                    __typename
                    ... on AdminIntegrationClientRotateSecretSuccess {
                        clientSecret
                        integrationClient { id status }
                    }
                    ... on AdminIntegrationClientUpdateProblem {
                        fields { name message }
                    }
                }
            }
        }
        """
        rotate_result = self.execute(rotate, {"id": integration_client.id})
        self.assertIsNone(rotate_result.errors, rotate_result.errors)
        rotate_payload = rotate_result.data["adminIntegrationClientRotateSecret"][
            "result"
        ]
        self.assertEqual(
            "AdminIntegrationClientRotateSecretSuccess",
            rotate_payload["__typename"],
        )
        self.assertTrue(rotate_payload["clientSecret"])
        self.assertNotEqual(payload["clientSecret"], rotate_payload["clientSecret"])

        disable = """
        mutation disableClient($id: ID!) {
            adminIntegrationClientDisable(id: $id) {
                result {
                    __typename
                    ... on AdminIntegrationClientUpdateSuccess {
                        integrationClient { id status }
                    }
                    ... on AdminIntegrationClientUpdateProblem {
                        fields { name message }
                    }
                }
            }
        }
        """
        disable_result = self.execute(disable, {"id": integration_client.id})
        self.assertIsNone(disable_result.errors, disable_result.errors)
        self.assertEqual(
            IntegrationClient.Status.DISABLED,
            disable_result.data["adminIntegrationClientDisable"]["result"][
                "integrationClient"
            ]["status"],
        )
        integration_client.refresh_from_db()
        self.assertEqual(IntegrationClient.Status.DISABLED, integration_client.status)

    def test_superuser_can_create_and_disable_webhook_endpoint(self):
        integration_client = self.create_client()
        options_result = self.execute(
            """
            query webhookEndpointStatusOptions {
                webhookEndpointStatusOptions { code label }
            }
            """
        )
        self.assertIsNone(options_result.errors, options_result.errors)
        self.assertEqual(
            [WebhookEndpoint.Status.ACTIVE, WebhookEndpoint.Status.DISABLED],
            [
                option["code"]
                for option in options_result.data["webhookEndpointStatusOptions"]
            ],
        )
        mutation = """
        mutation createWebhook($input: AdminWebhookEndpointInput!) {
            adminWebhookEndpointCreate(input: $input) {
                result {
                    __typename
                    ... on AdminWebhookEndpointCreateSuccess {
                        webhookEndpoint {
                            id
                            name
                            url
                            status
                            eventTypes
                            schemaVersion
                            customHeaders
                            integrationClient { code }
                        }
                    }
                    ... on AdminWebhookEndpointCreateProblem {
                        fields { name message }
                    }
                }
            }
        }
        """
        secret_header_result = self.execute(
            mutation,
            {
                "input": {
                    "integrationClientId": integration_client.id,
                    "name": "bad-secret-header",
                    "url": "https://external.example.test/webhook",
                    "eventTypes": [IntegrationEventType.REPORT_SUBMITTED],
                    "customHeaders": {"X-Api-Key": "plain"},
                }
            },
        )
        self.assertIsNone(secret_header_result.errors, secret_header_result.errors)
        self.assertEqual(
            "AdminWebhookEndpointCreateProblem",
            secret_header_result.data["adminWebhookEndpointCreate"]["result"][
                "__typename"
            ],
        )
        self.assertEqual(0, WebhookEndpoint.objects.count())

        create_result = self.execute(
            mutation,
            {
                "input": {
                    "integrationClientId": integration_client.id,
                    "name": "report-submitted",
                    "url": "https://external.example.test/webhook",
                    "eventTypes": [IntegrationEventType.REPORT_SUBMITTED],
                    "activeSigningSecretRef": "secret-manager://tenant/ai/active",
                    "activeSigningSecretVersion": 2,
                    "customHeaders": {"X-Correlation-ID": "trace-1"},
                }
            },
        )
        self.assertIsNone(create_result.errors, create_result.errors)
        payload = create_result.data["adminWebhookEndpointCreate"]["result"]
        self.assertEqual("AdminWebhookEndpointCreateSuccess", payload["__typename"])
        self.assertEqual(
            [IntegrationEventType.REPORT_SUBMITTED],
            payload["webhookEndpoint"]["eventTypes"],
        )
        self.assertEqual(
            {"X-Correlation-ID": "trace-1"},
            payload["webhookEndpoint"]["customHeaders"],
        )
        webhook_endpoint = WebhookEndpoint.objects.get()

        disable = """
        mutation disableWebhook($id: ID!) {
            adminWebhookEndpointDisable(id: $id) {
                result {
                    __typename
                    ... on AdminWebhookEndpointUpdateSuccess {
                        webhookEndpoint { id status }
                    }
                    ... on AdminWebhookEndpointUpdateProblem {
                        fields { name message }
                    }
                }
            }
        }
        """
        disable_result = self.execute(disable, {"id": webhook_endpoint.id})
        self.assertIsNone(disable_result.errors, disable_result.errors)
        self.assertEqual(
            WebhookEndpoint.Status.DISABLED,
            disable_result.data["adminWebhookEndpointDisable"]["result"][
                "webhookEndpoint"
            ]["status"],
        )
        webhook_endpoint.refresh_from_db()
        self.assertEqual(WebhookEndpoint.Status.DISABLED, webhook_endpoint.status)

    def test_superuser_can_update_tenant_wide_integration_policy(self):
        mutation = """
        mutation updatePolicy($input: AdminIntegrationPolicyInput!) {
            adminIntegrationPolicyUpdate(input: $input) {
                result {
                    __typename
                    ... on AdminIntegrationPolicyUpdateSuccess {
                        policy {
                            integrationEnabled
                            aiEnabled
                            riskEvaluatorEnabled
                            clusterDetectorEnabled
                            aiDefaultCommentOwnerUserId
                            aiDefaultCommentOwnerName
                            dashboardRiskWindowDays
                        }
                    }
                    ... on AdminIntegrationPolicyUpdateProblem {
                        fields { name message }
                    }
                }
            }
        }
        """
        result = self.execute(
            mutation,
            {
                "input": {
                    "integrationEnabled": True,
                    "aiEnabled": True,
                    "riskEvaluatorEnabled": True,
                    "clusterDetectorEnabled": False,
                    "aiDefaultCommentOwnerUserId": self.admin_owner.id,
                    "dashboardRiskWindowDays": 14,
                }
            },
        )

        self.assertIsNone(result.errors, result.errors)
        payload = result.data["adminIntegrationPolicyUpdate"]["result"]
        self.assertEqual("AdminIntegrationPolicyUpdateSuccess", payload["__typename"])
        policy = payload["policy"]
        self.assertTrue(policy["integrationEnabled"])
        self.assertTrue(policy["aiEnabled"])
        self.assertTrue(policy["riskEvaluatorEnabled"])
        self.assertFalse(policy["clusterDetectorEnabled"])
        self.assertEqual(str(self.admin_owner.id), policy["aiDefaultCommentOwnerUserId"])
        self.assertEqual("Tenant Admin", policy["aiDefaultCommentOwnerName"])
        self.assertEqual(14, policy["dashboardRiskWindowDays"])
        self.assertEqual(
            FEATURE_ENABLED_VALUE,
            Configuration.objects.get(key=INTEGRATION_ENABLED_KEY).value,
        )
        self.assertEqual(
            FEATURE_ENABLED_VALUE,
            Configuration.objects.get(key=AI_ENABLED_KEY).value,
        )
        self.assertEqual(
            FEATURE_ENABLED_VALUE,
            Configuration.objects.get(key=RISK_EVALUATOR_ENABLED_KEY).value,
        )
        self.assertEqual(
            str(self.admin_owner.id),
            Configuration.objects.get(key=AI_DEFAULT_COMMENT_OWNER_USER_ID_KEY).value,
        )
        self.assertEqual(
            "14",
            Configuration.objects.get(key=DASHBOARD_RISK_WINDOW_DAYS_KEY).value,
        )
        self.assertTrue(
            Configuration.objects.filter(key=CLUSTER_DETECTOR_ENABLED_KEY).exists()
        )

    def test_policy_rejects_non_admin_default_comment_owner(self):
        reporter = AuthorityUser.objects.create(
            username="reporter",
            authority=self.authority,
            role=AuthorityUser.Role.REPORTER,
        )
        mutation = """
        mutation updatePolicy($input: AdminIntegrationPolicyInput!) {
            adminIntegrationPolicyUpdate(input: $input) {
                result {
                    __typename
                    ... on AdminIntegrationPolicyUpdateSuccess {
                        policy { integrationEnabled }
                    }
                    ... on AdminIntegrationPolicyUpdateProblem {
                        fields { name message }
                    }
                }
            }
        }
        """
        result = self.execute(
            mutation,
            {
                "input": {
                    "integrationEnabled": True,
                    "aiEnabled": True,
                    "riskEvaluatorEnabled": True,
                    "clusterDetectorEnabled": True,
                    "aiDefaultCommentOwnerUserId": reporter.id,
                    "dashboardRiskWindowDays": 7,
                }
            },
        )

        self.assertIsNone(result.errors, result.errors)
        payload = result.data["adminIntegrationPolicyUpdate"]["result"]
        self.assertEqual("AdminIntegrationPolicyUpdateProblem", payload["__typename"])
        self.assertEqual(
            "aiDefaultCommentOwnerUserId",
            payload["fields"][0]["name"],
        )

    def test_non_superuser_cannot_access_integration_admin_contract(self):
        query = """
        query integrationPolicyGet {
            integrationPolicyGet {
                integrationEnabled
            }
        }
        """
        result = self.execute(query, user=self.normal_user)
        self.assertIsNotNone(result.errors)
        self.assertIn("Permission denied", str(result.errors[0]))

        mutation = """
        mutation createClient($input: AdminIntegrationClientInput!) {
            adminIntegrationClientCreate(input: $input) {
                result {
                    __typename
                    ... on AdminIntegrationClientCreateSuccess {
                        clientSecret
                    }
                    ... on AdminIntegrationClientCreateProblem {
                        fields { name message }
                    }
                }
            }
        }
        """
        mutation_result = self.execute(
            mutation,
            {
                "input": {
                    "name": "AI Assistant",
                    "code": "ai-assistant",
                    "integrationType": "AI_ASSISTANT",
                    "scopeCodes": [IntegrationScope.AI_READ_REPORT],
                }
            },
            user=self.normal_user,
        )
        self.assertIsNotNone(mutation_result.errors)
        self.assertEqual(0, IntegrationClient.objects.count())
