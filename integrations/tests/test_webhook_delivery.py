import hmac
import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone as datetime_timezone
from unittest import mock

from django.db import IntegrityError, connection, transaction
from django.test import SimpleTestCase, override_settings
from django.urls import get_resolver
from django.utils import timezone
from django_tenants.test.cases import TenantTestCase
from oauth2_provider.models import get_application_model

from accounts.models import Authority, AuthorityUser
from integrations.constants import IntegrationEventType, IntegrationScope
from integrations.models import (
    IntegrationClient,
    IntegrationEvent,
    WebhookDelivery,
    WebhookEndpoint,
)
from integrations.webhooks import (
    WebhookHttpResponse,
    attempt_webhook_delivery_by_id,
    build_report_submitted_payload,
    record_report_submitted_event,
)
from reports.models import Category, IncidentReport, ReportType
from reports.signals import incident_report_submitted


class WebhookBoundaryTests(SimpleTestCase):
    def test_webhook_delivery_does_not_add_external_url_surface(self):
        url_patterns = " ".join(
            str(pattern.pattern).lower() for pattern in get_resolver().url_patterns
        )

        self.assertNotIn("webhook", url_patterns)
        self.assertNotIn("deliver", url_patterns)


@dataclass
class CapturingWebhookHttpClient:
    status_code: int = 204
    body: str = ""
    calls: list = None

    def __post_init__(self):
        if self.calls is None:
            self.calls = []

    def send(self, *, url, headers, body, timeout):
        self.calls.append(
            {
                "url": url,
                "headers": headers,
                "body": body,
                "timeout": timeout,
            }
        )
        return WebhookHttpResponse(status_code=self.status_code, body=self.body)


class WebhookDeliveryTests(TenantTestCase):
    @classmethod
    def setup_tenant(cls, tenant):
        tenant.name = "Tenant Alpha"

    def setUp(self):
        self.authority = Authority.objects.create(code="BKK", name="Bangkok")
        self.reporter = AuthorityUser.objects.create(
            username="reporter",
            authority=self.authority,
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
        )
        self.report.relevant_authorities.add(self.authority)

    def test_signal_enqueues_report_submitted_event_task(self):
        with mock.patch(
            "integrations.tasks.record_report_submitted_event.delay"
        ) as enqueue:
            incident_report_submitted.send(sender=IncidentReport, report=self.report)

        enqueue.assert_called_once_with(self.report.id)

    def test_records_event_and_creates_deliveries_for_active_subscribers_only(self):
        active_client = self._create_integration_client("ai-active")
        active_endpoint = self._create_endpoint(
            active_client,
            name="report-submitted",
            event_types=[IntegrationEventType.REPORT_SUBMITTED],
        )
        self._create_endpoint(
            active_client,
            name="other-event",
            event_types=[IntegrationEventType.FOLLOWUP_SUBMITTED],
        )
        self._create_endpoint(
            active_client,
            name="disabled-endpoint",
            event_types=[IntegrationEventType.REPORT_SUBMITTED],
            status=WebhookEndpoint.Status.DISABLED,
        )
        disabled_client = self._create_integration_client(
            "ai-disabled",
            status=IntegrationClient.Status.DISABLED,
        )
        self._create_endpoint(
            disabled_client,
            name="disabled-client-endpoint",
            event_types=[IntegrationEventType.REPORT_SUBMITTED],
        )
        no_scope_client = self._create_integration_client(
            "ai-no-report-read",
            scope_codes=[],
        )
        self._create_endpoint(
            no_scope_client,
            name="no-scope-endpoint",
            event_types=[IntegrationEventType.REPORT_SUBMITTED],
        )

        result = record_report_submitted_event(
            report_id=self.report.id,
            enqueue_delivery_tasks=False,
        )

        self.assertEqual(IntegrationEventType.REPORT_SUBMITTED, result.event.event_type)
        self.assertEqual(IntegrationEvent.Status.QUEUED, result.event.status)
        self.assertEqual("reports", result.event.source_app)
        self.assertEqual("reports.IncidentReport", result.event.subject_type)
        self.assertEqual(str(self.report.id), result.event.subject_id)
        self.assertEqual(1, len(result.deliveries))
        self.assertEqual(active_endpoint, result.deliveries[0].endpoint)
        self.assertEqual(result.event.payload_hash, result.deliveries[0].payload_hash)
        self.assertEqual(
            [self.authority.id],
            result.event.payload_summary["report"]["relevantAuthorityIds"],
        )
        self.assertEqual(
            str(self.report.id),
            result.event.payload_summary["report"]["id"],
        )
        self.assertNotIn("data", result.event.payload_summary["report"])
        self.assertNotIn("private-input", str(result.event.payload_summary))

    def test_recording_can_enqueue_delivery_attempt_tasks(self):
        active_client = self._create_integration_client("ai-queued")
        self._create_endpoint(
            active_client,
            name="report-submitted",
            event_types=[IntegrationEventType.REPORT_SUBMITTED],
        )

        with mock.patch("integrations.tasks.attempt_webhook_delivery.delay") as enqueue:
            result = record_report_submitted_event(
                report_id=self.report.id,
                enqueue_delivery_tasks=True,
            )

        enqueue.assert_called_once_with(result.deliveries[0].id)

    def test_recording_replay_enqueues_existing_pending_delivery(self):
        active_client = self._create_integration_client("ai-replay")
        self._create_endpoint(
            active_client,
            name="report-submitted",
            event_types=[IntegrationEventType.REPORT_SUBMITTED],
        )
        first = record_report_submitted_event(
            report_id=self.report.id,
            enqueue_delivery_tasks=False,
        )

        with mock.patch("integrations.tasks.attempt_webhook_delivery.delay") as enqueue:
            second = record_report_submitted_event(
                report_id=self.report.id,
                enqueue_delivery_tasks=True,
            )

        self.assertEqual(first.event.id, second.event.id)
        self.assertEqual(first.event.event_id, second.event.event_id)
        self.assertEqual(1, len(second.deliveries))
        self.assertEqual(first.deliveries[0].id, second.deliveries[0].id)
        enqueue.assert_called_once_with(first.deliveries[0].id)

    def test_report_submitted_event_has_database_idempotency_key(self):
        active_client = self._create_integration_client("ai-idempotency")
        self._create_endpoint(
            active_client,
            name="report-submitted",
            event_types=[IntegrationEventType.REPORT_SUBMITTED],
        )
        result = record_report_submitted_event(
            report_id=self.report.id,
            enqueue_delivery_tasks=False,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                IntegrationEvent.objects.create(
                    event_type=IntegrationEventType.REPORT_SUBMITTED,
                    source_app="reports",
                    subject_type="reports.IncidentReport",
                    subject_id=str(self.report.id),
                    payload_hash=result.event.payload_hash,
                    payload_summary=result.event.payload_summary,
                    produced_at=timezone.now(),
                )

        replay = record_report_submitted_event(
            report_id=self.report.id,
            enqueue_delivery_tasks=False,
        )
        self.assertEqual(result.event.id, replay.event.id)
        self.assertEqual(
            1,
            IntegrationEvent.objects.filter(
                event_type=IntegrationEventType.REPORT_SUBMITTED,
                source_app="reports",
                subject_type="reports.IncidentReport",
                subject_id=str(self.report.id),
            ).count(),
        )

    @override_settings(
        INTEGRATION_WEBHOOK_SIGNING_SECRETS={
            "secret-manager://tenant/ai/active": {
                "value": "plain-signing-secret",
                "key_id": "ai-active-key",
            }
        }
    )
    def test_delivery_success_signs_headers_and_does_not_store_plaintext_secret(self):
        active_client = self._create_integration_client("ai-sign")
        endpoint = self._create_endpoint(
            active_client,
            name="report-submitted",
            url="https://external.example.test/webhook/path?source=ohtk",
            event_types=[IntegrationEventType.REPORT_SUBMITTED],
            active_signing_secret_ref="secret-manager://tenant/ai/active",
            active_signing_secret_version=3,
            custom_headers={"X-Correlation-ID": "trace-1"},
        )
        result = record_report_submitted_event(
            report_id=self.report.id,
            enqueue_delivery_tasks=False,
        )
        delivery = result.deliveries[0]
        timestamp = datetime(2026, 6, 2, 6, 0, tzinfo=datetime_timezone.utc)
        http_client = CapturingWebhookHttpClient(status_code=204, body="")

        updated = attempt_webhook_delivery_by_id(
            delivery.id,
            http_client=http_client,
            timestamp=timestamp,
        )

        self.assertEqual(WebhookDelivery.Status.SUCCEEDED, updated.status)
        self.assertEqual(1, updated.attempt_count)
        self.assertEqual(204, updated.response_status_code)
        self.assertIsNone(updated.next_retry_at)
        self.assertEqual(3, updated.signing_secret_version)
        call = http_client.calls[0]
        headers = call["headers"]
        self.assertEqual(str(result.event.event_id), headers["X-OHTK-Event-ID"])
        self.assertEqual("ai-sign", headers["X-OHTK-Integration"])
        self.assertEqual(connection.schema_name, headers["X-OHTK-Tenant"])
        self.assertEqual("ai-active-key", headers["X-OHTK-Signing-Key-ID"])
        self.assertEqual("3", headers["X-OHTK-Signing-Secret-Version"])
        self.assertEqual("trace-1", headers["X-Correlation-ID"])
        self.assertEqual(endpoint.timeout_seconds, call["timeout"])

        expected_message = b"\n".join(
            [
                b"POST",
                b"/webhook/path?source=ohtk",
                timestamp.isoformat().encode("utf-8"),
                call["body"],
            ]
        )
        expected_signature = hmac.new(
            b"plain-signing-secret",
            expected_message,
            hashlib.sha256,
        ).hexdigest()
        self.assertEqual(expected_signature, headers["X-OHTK-Signature"])
        self.assertNotIn("plain-signing-secret", str(endpoint.__dict__))
        updated.refresh_from_db()
        self.assertNotIn("plain-signing-secret", str(updated.__dict__))

    @override_settings(
        INTEGRATION_WEBHOOK_SIGNING_SECRETS={
            "secret-manager://tenant/ai/active": "plain-signing-secret"
        }
    )
    def test_duplicate_delivery_task_does_not_send_when_already_claimed(self):
        active_client = self._create_integration_client("ai-duplicate")
        self._create_endpoint(
            active_client,
            name="report-submitted",
            event_types=[IntegrationEventType.REPORT_SUBMITTED],
        )
        result = record_report_submitted_event(
            report_id=self.report.id,
            enqueue_delivery_tasks=False,
        )
        delivery = result.deliveries[0]
        delivery.status = WebhookDelivery.Status.DELIVERING
        delivery.save(update_fields=("status",))
        http_client = CapturingWebhookHttpClient(status_code=204, body="")

        updated = attempt_webhook_delivery_by_id(
            delivery.id,
            http_client=http_client,
        )

        self.assertEqual(WebhookDelivery.Status.DELIVERING, updated.status)
        self.assertEqual(0, len(http_client.calls))

    @override_settings(
        INTEGRATION_WEBHOOK_SIGNING_SECRETS={
            "secret-manager://tenant/ai/active": "plain-signing-secret"
        }
    )
    def test_duplicate_delivery_task_cannot_send_while_first_task_is_sending(self):
        active_client = self._create_integration_client("ai-concurrent")
        self._create_endpoint(
            active_client,
            name="report-submitted",
            event_types=[IntegrationEventType.REPORT_SUBMITTED],
        )
        result = record_report_submitted_event(
            report_id=self.report.id,
            enqueue_delivery_tasks=False,
        )
        nested_client = CapturingWebhookHttpClient(status_code=204, body="")

        class ReentrantClient(CapturingWebhookHttpClient):
            def send(inner_self, *, url, headers, body, timeout):
                attempt_webhook_delivery_by_id(
                    result.deliveries[0].id,
                    http_client=nested_client,
                )
                return super().send(
                    url=url,
                    headers=headers,
                    body=body,
                    timeout=timeout,
                )

        outer_client = ReentrantClient(status_code=204, body="")

        updated = attempt_webhook_delivery_by_id(
            result.deliveries[0].id,
            http_client=outer_client,
        )

        self.assertEqual(WebhookDelivery.Status.SUCCEEDED, updated.status)
        self.assertEqual(1, len(outer_client.calls))
        self.assertEqual(0, len(nested_client.calls))

    @override_settings(
        INTEGRATION_WEBHOOK_SIGNING_SECRETS={
            "secret-manager://tenant/ai/failure": "plain-failure-secret"
        }
    )
    def test_delivery_failure_records_safe_response_summary_and_retry_metadata(self):
        active_client = self._create_integration_client("ai-fail")
        self._create_endpoint(
            active_client,
            name="report-submitted",
            event_types=[IntegrationEventType.REPORT_SUBMITTED],
            active_signing_secret_ref="secret-manager://tenant/ai/failure",
            retry_policy={"initial_delay_seconds": 60},
            max_attempts=3,
        )
        result = record_report_submitted_event(
            report_id=self.report.id,
            enqueue_delivery_tasks=False,
        )
        http_client = CapturingWebhookHttpClient(
            status_code=500,
            body='{"token": "plain-token", "message": "failed"}',
        )
        timestamp = datetime(2026, 6, 2, 6, 0, tzinfo=datetime_timezone.utc)

        updated = attempt_webhook_delivery_by_id(
            result.deliveries[0].id,
            http_client=http_client,
            timestamp=timestamp,
        )

        self.assertEqual(WebhookDelivery.Status.FAILED, updated.status)
        self.assertEqual(1, updated.attempt_count)
        self.assertEqual(500, updated.response_status_code)
        self.assertEqual("HTTP 500", updated.failure_reason)
        self.assertEqual(
            {"token": "[REDACTED]", "message": "failed"},
            updated.response_body_summary,
        )
        self.assertEqual(timestamp + timedelta(seconds=60), updated.next_retry_at)
        self.assertNotIn("plain-token", str(updated.response_body_summary))
        self.assertNotIn("plain-failure-secret", str(updated.__dict__))

    def test_delivery_without_configured_secret_fails_without_plaintext_model_storage(self):
        active_client = self._create_integration_client("ai-missing-secret")
        self._create_endpoint(
            active_client,
            name="report-submitted",
            event_types=[IntegrationEventType.REPORT_SUBMITTED],
            active_signing_secret_ref="secret-manager://tenant/ai/missing",
        )
        result = record_report_submitted_event(
            report_id=self.report.id,
            enqueue_delivery_tasks=False,
        )

        delivery = result.deliveries[0]
        delivery.response_status_code = 500
        delivery.response_body_summary = {"message": "stale"}
        delivery.next_retry_at = timezone.now() + timedelta(hours=1)
        delivery.save(
            update_fields=(
                "response_status_code",
                "response_body_summary",
                "next_retry_at",
            )
        )

        updated = attempt_webhook_delivery_by_id(delivery.id)

        self.assertEqual(WebhookDelivery.Status.FAILED, updated.status)
        self.assertEqual(0, updated.attempt_count)
        self.assertIn("not configured", updated.failure_reason)
        self.assertIsNone(updated.next_retry_at)
        self.assertIsNone(updated.response_status_code)
        self.assertEqual({}, updated.response_body_summary)
        self.assertFalse(
            any(field.name == "signing_secret" for field in WebhookEndpoint._meta.fields)
        )

    def test_build_report_submitted_payload_uses_thin_report_shape(self):
        event_id = "3f5c8162-7364-42eb-9182-35049dfe12bd"
        produced_at = datetime(2026, 6, 2, 6, 0, tzinfo=datetime_timezone.utc)

        payload = build_report_submitted_payload(
            report=self.report,
            event_id=event_id,
            produced_at=produced_at,
        )

        self.assertEqual("2026-06-02", payload["schemaVersion"])
        self.assertEqual(IntegrationEventType.REPORT_SUBMITTED, payload["eventType"])
        self.assertEqual(event_id, payload["eventId"])
        self.assertEqual(connection.schema_name, payload["tenant"]["schema"])
        self.assertEqual(str(self.report.id), payload["report"]["id"])
        self.assertEqual("Animal Sick/Death", payload["report"]["reportType"]["name"])
        self.assertEqual([self.authority.id], payload["report"]["relevantAuthorityIds"])
        self.assertNotIn("data", payload["report"])

    def _create_integration_client(
        self,
        code,
        status=IntegrationClient.Status.ACTIVE,
        scope_codes=None,
    ):
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
            status=status,
            scope_codes=(
                [IntegrationScope.AI_READ_REPORT]
                if scope_codes is None
                else scope_codes
            ),
        )

    def _create_endpoint(
        self,
        integration_client,
        *,
        name,
        event_types,
        url="https://external.example.test/webhook",
        status=WebhookEndpoint.Status.ACTIVE,
        active_signing_secret_ref="secret-manager://tenant/ai/active",
        active_signing_secret_version=1,
        custom_headers=None,
        retry_policy=None,
        max_attempts=5,
    ):
        return WebhookEndpoint.objects.create(
            integration_client=integration_client,
            name=name,
            url=url,
            event_types=event_types,
            status=status,
            active_signing_secret_ref=active_signing_secret_ref,
            active_signing_secret_version=active_signing_secret_version,
            custom_headers=custom_headers or {},
            retry_policy=retry_policy or {},
            max_attempts=max_attempts,
        )
