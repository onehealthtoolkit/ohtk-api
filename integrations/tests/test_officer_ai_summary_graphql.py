from django.test import RequestFactory
from django.utils import timezone
from django_tenants.test.cases import TenantTestCase
from oauth2_provider.models import get_application_model

from accounts.models import Authority, AuthorityUser, User
from integrations.constants import IntegrationEventType, IntegrationScope
from integrations.models import IntegrationClient, WebhookEndpoint
from integrations.policy import set_integration_policy
from podd_api.schema import schema
from reports.models import Category, IncidentReport, ReportType


class OfficerAiSummaryGraphqlTests(TenantTestCase):
    @classmethod
    def setup_tenant(cls, tenant):
        tenant.name = "Tenant Alpha"

    def setUp(self):
        self.request_factory = RequestFactory()
        self.authority = Authority.objects.create(code="BKK", name="Bangkok")
        self.admin = AuthorityUser.objects.create(
            username="L01",
            authority=self.authority,
            role=AuthorityUser.Role.ADMIN,
        )
        self.officer = AuthorityUser.objects.create(
            username="V01",
            authority=self.authority,
            role=AuthorityUser.Role.OFFICER,
        )
        self.reporter = AuthorityUser.objects.create(
            username="reporter",
            authority=self.authority,
            role=AuthorityUser.Role.REPORTER,
        )
        self.super_user = User.objects.create(username="platform", is_superuser=True)
        self.category = Category.objects.create(name="animal")
        self.report_type = ReportType.objects.create(
            name="Animal Sick/Death",
            category=self.category,
            definition={},
            published=True,
        )
        self.report = IncidentReport.objects.create(
            data={"symptom": "cough"},
            reported_by=self.reporter,
            incident_date=timezone.datetime(2026, 6, 2).date(),
            report_type=self.report_type,
        )
        self.report.relevant_authorities.add(self.authority)
        set_integration_policy(
            integration_enabled=True,
            ai_enabled=True,
            risk_evaluator_enabled=True,
            cluster_detector_enabled=True,
            ai_default_comment_owner_user_id="",
            dashboard_risk_window_days=7,
        )
        self._create_endpoint()

    def test_officer_can_queue_summary_with_prompt(self):
        result = self.execute(
            """
            mutation request($reportId: UUID!, $userPrompt: String) {
              officerAiSummaryRequest(reportId: $reportId, userPrompt: $userPrompt) {
                result {
                  __typename
                  ... on OfficerAiSummaryRequestSuccess {
                    eventId
                    reportId
                    status
                  }
                  ... on OfficerAiSummaryRequestProblem {
                    code
                    message
                  }
                }
              }
            }
            """,
            {
                "reportId": str(self.report.id),
                "userPrompt": "Focus on deaths",
            },
            user=self.officer,
        )
        self.assertIsNone(result.errors)
        payload = result.data["officerAiSummaryRequest"]["result"]
        self.assertEqual("OfficerAiSummaryRequestSuccess", payload["__typename"])
        self.assertEqual("queued", payload["status"])
        self.assertEqual(str(self.report.id), payload["reportId"])

    def test_reporter_is_denied_and_me_flag_is_false(self):
        denied = self.execute(
            """
            mutation request($reportId: UUID!) {
              officerAiSummaryRequest(reportId: $reportId) {
                result {
                  __typename
                  ... on OfficerAiSummaryRequestProblem { code }
                }
              }
            }
            """,
            {"reportId": str(self.report.id)},
            user=self.reporter,
        )
        self.assertEqual(
            "permission_denied",
            denied.data["officerAiSummaryRequest"]["result"]["code"],
        )

        me = self.execute("{ me { aiSummaryEnabled role } }", user=self.reporter)
        self.assertFalse(me.data["me"]["aiSummaryEnabled"])
        admin_me = self.execute("{ me { aiSummaryEnabled } }", user=self.admin)
        self.assertTrue(admin_me.data["me"]["aiSummaryEnabled"])
        super_me = self.execute("{ me { aiSummaryEnabled } }", user=self.super_user)
        self.assertTrue(super_me.data["me"]["aiSummaryEnabled"])

    def test_me_flag_false_when_ai_disabled(self):
        set_integration_policy(
            integration_enabled=True,
            ai_enabled=False,
            risk_evaluator_enabled=True,
            cluster_detector_enabled=True,
            ai_default_comment_owner_user_id="",
            dashboard_risk_window_days=7,
        )
        me = self.execute("{ me { aiSummaryEnabled } }", user=self.admin)
        self.assertFalse(me.data["me"]["aiSummaryEnabled"])

    def test_me_flag_follows_integrations_ai_enabled_only(self):
        from accounts.models import Configuration
        from integrations.policy import AI_ENABLED_KEY, INTEGRATION_ENABLED_KEY

        Configuration.objects.filter(key=AI_ENABLED_KEY).delete()
        me_missing = self.execute("{ me { aiSummaryEnabled } }", user=self.admin)
        self.assertFalse(me_missing.data["me"]["aiSummaryEnabled"])

        set_integration_policy(
            integration_enabled=False,
            ai_enabled=True,
            risk_evaluator_enabled=True,
            cluster_detector_enabled=True,
            ai_default_comment_owner_user_id="",
            dashboard_risk_window_days=7,
        )
        self.assertEqual(
            "disable",
            Configuration.objects.get(key=INTEGRATION_ENABLED_KEY).value,
        )
        me_ai_only = self.execute("{ me { aiSummaryEnabled } }", user=self.admin)
        self.assertTrue(me_ai_only.data["me"]["aiSummaryEnabled"])

    def execute(self, query, variables=None, user=None):
        request = self.request_factory.post("/graphql/")
        request.user = user or self.admin
        return schema.execute(
            query, variable_values=variables or {}, context_value=request
        )

    def _create_endpoint(self):
        application_model = get_application_model()
        application = application_model.objects.create(
            name="ai-summary",
            user=None,
            client_type=application_model.CLIENT_CONFIDENTIAL,
            authorization_grant_type=application_model.GRANT_CLIENT_CREDENTIALS,
        )
        client = IntegrationClient.objects.create(
            name="ai-summary",
            code="ai-summary",
            integration_type=IntegrationClient.IntegrationType.AI_ASSISTANT,
            oauth_application=application,
            scope_codes=[IntegrationScope.AI_READ_REPORT],
        )
        return WebhookEndpoint.objects.create(
            integration_client=client,
            name="ai-summary-hook",
            url="https://external.example.test/webhook",
            event_types=[IntegrationEventType.AI_EVALUATION_REQUESTED],
            status=WebhookEndpoint.Status.ACTIVE,
            active_signing_secret_ref="secret-manager://tenant/ai/active",
            active_signing_secret_version=1,
        )
