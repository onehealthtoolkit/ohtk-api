from unittest import mock
from uuid import uuid4

from django.utils import timezone
from django_tenants.test.cases import TenantTestCase
from oauth2_provider.models import get_application_model

from accounts.models import Authority, AuthorityUser
from integrations.ai_summary import (
    AiSummaryRequestError,
    request_officer_ai_summary,
)
from integrations.constants import IntegrationEventType, IntegrationScope
from integrations.models import IntegrationClient, IntegrationEvent, WebhookEndpoint
from integrations.policy import set_integration_policy
from integrations.webhooks import record_ai_evaluation_requested_event
from reports.models import Category, IncidentReport, ReportType


class AiEvaluationWebhookTests(TenantTestCase):
    @classmethod
    def setup_tenant(cls, tenant):
        tenant.name = "Tenant Alpha"

    def setUp(self):
        self.authority = Authority.objects.create(code="BKK", name="Bangkok")
        self.admin = AuthorityUser.objects.create(
            username="L01",
            authority=self.authority,
            role=AuthorityUser.Role.ADMIN,
        )
        self.reporter = AuthorityUser.objects.create(
            username="reporter",
            authority=self.authority,
            role=AuthorityUser.Role.REPORTER,
        )
        self.category = Category.objects.create(name="animal")
        self.report_type = ReportType.objects.create(
            name="Animal Sick/Death",
            category=self.category,
            definition={},
            published=True,
        )
        self.report_type.authorities.add(self.authority)
        self.report = IncidentReport.objects.create(
            data={"symptom": "cough", "token": "private-input"},
            reported_by=self.reporter,
            incident_date=timezone.datetime(2026, 6, 2).date(),
            report_type=self.report_type,
            renderer_data="should-not-be-in-webhook",
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

    def test_records_event_and_enqueues_active_ai_endpoint_only(self):
        client = self._create_client("ai-active")
        endpoint = self._create_endpoint(
            client, event_types=[IntegrationEventType.AI_EVALUATION_REQUESTED]
        )
        self._create_endpoint(
            client, name="report-only", event_types=[IntegrationEventType.REPORT_SUBMITTED]
        )
        no_scope = self._create_client("ai-no-scope", scope_codes=[])
        self._create_endpoint(
            no_scope, event_types=[IntegrationEventType.AI_EVALUATION_REQUESTED]
        )

        with mock.patch("integrations.tasks.attempt_webhook_delivery.delay") as enqueue:
            result = record_ai_evaluation_requested_event(
                report_id=self.report.id,
                requested_by_user=self.admin,
                user_prompt="  Focus on deaths.  ",
                enqueue_delivery_tasks=True,
            )

        enqueue.assert_called_once_with(result.deliveries[0].id)
        self.assertEqual(1, len(result.deliveries))
        self.assertEqual(endpoint, result.deliveries[0].endpoint)
        payload = result.event.payload_summary
        self.assertEqual("ai.evaluation_requested", payload["eventType"])
        self.assertEqual("summary", payload["purpose"])
        self.assertEqual("Focus on deaths.", payload["userPrompt"])
        self.assertEqual(self.admin.username, payload["requestedBy"]["username"])
        self.assertEqual("ADM", payload["requestedBy"]["role"])
        self.assertNotIn("data", payload["report"])
        self.assertNotIn("rendererData", payload["report"])
        self.assertNotIn("private-input", str(payload))
        self.assertNotIn("should-not-be-in-webhook", str(payload["report"]))
        self.assertIn("comments", payload["links"])
        self.assertIn("images", payload["links"])

    def test_blank_user_prompt_is_omitted(self):
        client = self._create_client("ai-blank")
        self._create_endpoint(
            client, event_types=[IntegrationEventType.AI_EVALUATION_REQUESTED]
        )

        result = record_ai_evaluation_requested_event(
            report_id=self.report.id,
            requested_by_user=self.admin,
            user_prompt="   ",
            enqueue_delivery_tasks=False,
        )

        self.assertNotIn("userPrompt", result.event.payload_summary)

    def test_does_not_collide_with_report_submitted_unique_event(self):
        client = self._create_client("ai-both")
        self._create_endpoint(
            client,
            event_types=[
                IntegrationEventType.REPORT_SUBMITTED,
                IntegrationEventType.AI_EVALUATION_REQUESTED,
            ],
        )
        from integrations.webhooks import record_report_submitted_event

        submitted = record_report_submitted_event(
            report_id=self.report.id, enqueue_delivery_tasks=False
        )
        requested = record_ai_evaluation_requested_event(
            report_id=self.report.id,
            requested_by_user=self.admin,
            enqueue_delivery_tasks=False,
        )
        self.assertIsNotNone(submitted.event)
        self.assertIsNotNone(requested.event)
        self.assertNotEqual(submitted.event.event_id, requested.event.event_id)
        self.assertEqual(2, IntegrationEvent.objects.count())

    def test_request_rejects_debounce_and_missing_endpoint(self):
        with self.assertRaises(AiSummaryRequestError) as missing:
            request_officer_ai_summary(
                user=self.admin,
                report_id=self.report.id,
                enqueue_delivery_tasks=False,
            )
        self.assertEqual("no_webhook_endpoint", missing.exception.code)

        client = self._create_client("ai-debounce")
        self._create_endpoint(
            client, event_types=[IntegrationEventType.AI_EVALUATION_REQUESTED]
        )
        first = request_officer_ai_summary(
            user=self.admin,
            report_id=self.report.id,
            enqueue_delivery_tasks=False,
        )
        self.assertEqual("queued", first["status"])
        with self.assertRaises(AiSummaryRequestError) as inflight:
            request_officer_ai_summary(
                user=self.admin,
                report_id=self.report.id,
                user_prompt="different prompt",
                enqueue_delivery_tasks=False,
            )
        self.assertEqual("already_in_flight", inflight.exception.code)

    def test_request_rejects_reporter_and_long_prompt(self):
        client = self._create_client("ai-auth")
        self._create_endpoint(
            client, event_types=[IntegrationEventType.AI_EVALUATION_REQUESTED]
        )
        with self.assertRaises(AiSummaryRequestError) as reporter:
            request_officer_ai_summary(
                user=self.reporter,
                report_id=self.report.id,
                enqueue_delivery_tasks=False,
            )
        self.assertEqual("permission_denied", reporter.exception.code)

        with self.assertRaises(AiSummaryRequestError) as too_long:
            request_officer_ai_summary(
                user=self.admin,
                report_id=self.report.id,
                user_prompt="x" * 2001,
                enqueue_delivery_tasks=False,
            )
        self.assertEqual("prompt_too_long", too_long.exception.code)

        with self.assertRaises(AiSummaryRequestError) as missing:
            request_officer_ai_summary(
                user=self.admin,
                report_id=uuid4(),
                enqueue_delivery_tasks=False,
            )
        self.assertEqual("incident_not_found", missing.exception.code)

    def test_request_rejects_disabled_policy(self):
        client = self._create_client("ai-policy")
        self._create_endpoint(
            client, event_types=[IntegrationEventType.AI_EVALUATION_REQUESTED]
        )
        set_integration_policy(
            integration_enabled=True,
            ai_enabled=False,
            risk_evaluator_enabled=True,
            cluster_detector_enabled=True,
            ai_default_comment_owner_user_id="",
            dashboard_risk_window_days=7,
        )
        with self.assertRaises(AiSummaryRequestError) as disabled:
            request_officer_ai_summary(
                user=self.admin,
                report_id=self.report.id,
                enqueue_delivery_tasks=False,
            )
        self.assertEqual("ai_disabled", disabled.exception.code)

    def _create_client(self, code, scope_codes=None):
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
            scope_codes=(
                [IntegrationScope.AI_READ_REPORT]
                if scope_codes is None
                else scope_codes
            ),
        )

    def _create_endpoint(self, integration_client, *, event_types, name=None):
        return WebhookEndpoint.objects.create(
            integration_client=integration_client,
            name=name or f"{integration_client.code}-endpoint",
            url="https://external.example.test/webhook",
            event_types=event_types,
            status=WebhookEndpoint.Status.ACTIVE,
            active_signing_secret_ref="secret-manager://tenant/ai/active",
            active_signing_secret_version=1,
        )
