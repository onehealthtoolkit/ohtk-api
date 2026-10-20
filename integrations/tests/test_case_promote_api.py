import json
from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

from django.db import connection
from django.test import Client, override_settings
from django.urls import resolve
from django.utils import timezone
from django_tenants.test.cases import TenantTestCase
from django_tenants.test.client import TenantClient
from django_tenants.utils import schema_context, tenant_context
from oauth2_provider.models import get_access_token_model, get_application_model

from accounts.models import Authority, AuthorityUser, Configuration
from cases.models import Case, CaseState, CaseStateMapping, StateDefinition, StateStep
from integrations.constants import IntegrationScope
from integrations.models import (
    IntegrationActionLog,
    IntegrationClient,
    IntegrationIdempotencyRecord,
)
from integrations.policy import AI_ENABLED_KEY, INTEGRATION_ENABLED_KEY
from reports.models import Category, IncidentReport, ReportType
from tenants.models import Client as Tenant, Domain


class CasePromoteApiTests(TenantTestCase):
    @classmethod
    def setup_tenant(cls, tenant):
        tenant.name = "Case promotion tenant"

    def setUp(self):
        # TenantTestCase skips Django's setUpClass, so class setting overrides
        # are not applied. Activate them for each test instead.
        settings_override = override_settings(
            ALLOWED_HOSTS=["localhost", "tenant.test.com", "promote-other.test"],
            CHANNEL_LAYERS={
                "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}
            },
        )
        settings_override.enable()
        self.addCleanup(settings_override.disable)
        connection.set_tenant(self.tenant)
        self.client = TenantClient(self.tenant)
        self.authority = Authority.objects.create(code="CASE", name="Case authority")
        self.reporter = AuthorityUser.objects.create(
            username="case-reporter", authority=self.authority
        )
        self.report_type = ReportType.objects.create(
            name="Animal Sick/Death",
            category=Category.objects.create(name="animal"),
            definition={},
            published=True,
        )
        self.report = self._report()
        self.definition = StateDefinition.objects.create(
            name="Default", is_default=True
        )
        self.start = StateStep.objects.create(
            name="Open", is_start_state=True, state_definition=self.definition
        )
        application_model = get_application_model()
        self.application = application_model.objects.create(
            name="case-ai",
            user=None,
            client_type=application_model.CLIENT_CONFIDENTIAL,
            authorization_grant_type=application_model.GRANT_CLIENT_CREDENTIALS,
        )
        self.integration_client = IntegrationClient.objects.create(
            name="Case AI",
            code="case-ai",
            integration_type=IntegrationClient.IntegrationType.AI_ASSISTANT,
            oauth_application=self.application,
            scope_codes=[IntegrationScope.CASE_PROMOTE],
        )
        self.token = get_access_token_model().objects.create(
            user=None,
            token="case-service-token",
            application=self.application,
            expires=timezone.now() + timedelta(hours=1),
            scope="",
        )
        notification_patch = patch(
            "cases.signals.tasks.evaluate_promote_to_case_notification.delay"
        )
        self.notification = notification_patch.start()
        self.addCleanup(notification_patch.stop)

    def _report(self):
        report = IncidentReport.objects.create(
            reported_by=self.reporter,
            report_type=self.report_type,
            incident_date=timezone.now().date(),
            data={},
        )
        report.relevant_authorities.add(self.authority)
        return report

    def _url(self, report_id=None):
        return (
            f"/api/integrations/v1/reports/{report_id or self.report.id}/promote-case"
        )

    def _post(self, payload=None, key=None, report_id=None):
        headers = {"HTTP_AUTHORIZATION": f"Bearer {self.token.token}"}
        if key is not None:
            headers["HTTP_IDEMPOTENCY_KEY"] = key
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(
                self._url(report_id),
                data=json.dumps(
                    {"externalActionId": "promote-1"} if payload is None else payload
                ),
                content_type="application/json",
                **headers,
            )

    def _assert_rejected(self, response, status, code):
        self.assertEqual(status, response.status_code)
        self.assertEqual(code, response.json()["error"]["code"])
        self.assertFalse(Case.objects.exists())
        self.assertFalse(IntegrationIdempotencyRecord.objects.exists())
        action = IntegrationActionLog.objects.get()
        self.assertEqual("case.promote", action.action_type)
        self.assertEqual(IntegrationScope.CASE_PROMOTE, action.required_scope)
        self.assertEqual(
            IntegrationActionLog.ResultStatus.REJECTED, action.result_status
        )
        self.assertEqual(code, action.result_summary["error"]["code"])

    def test_service_promotion_uses_existing_case_workflow_and_audits_identity(self):
        self.assertEqual(
            "integration-report-promote-case", resolve(self._url()).url_name
        )
        response = self._post()
        self.assertEqual(200, response.status_code)
        case = Case.objects.get()
        self.report.refresh_from_db()
        self.assertEqual(case.id, self.report.case_id)
        self.assertEqual(self.definition, case.state_definition)
        self.assertEqual("Open", case.status_label)
        self.assertEqual([self.authority], list(case.authorities.all()))
        self.assertEqual(self.start, CaseState.objects.get(case=case).state)
        self.assertEqual(
            {
                "schemaVersion": "2026-06-02",
                "status": "accepted",
                "case": {"id": str(case.id), "reportId": str(self.report.id)},
                "alreadyPromoted": False,
            },
            response.json(),
        )
        action = IntegrationActionLog.objects.get()
        self.assertEqual(self.integration_client, action.integration_client)
        self.assertEqual("case.promote", action.action_type)
        self.assertEqual(IntegrationScope.CASE_PROMOTE, action.required_scope)
        self.assertEqual("reports.IncidentReport", action.target_type)
        self.assertEqual(str(self.report.id), action.target_id)
        self.assertEqual("promote-1", action.external_action_id)
        self.assertEqual("promote-1", action.idempotency_key)
        self.assertEqual("[REDACTED]", action.request_headers_summary["Authorization"])
        self.assertEqual(
            IntegrationActionLog.ResultStatus.ACCEPTED, action.result_status
        )
        self.assertEqual(action, IntegrationIdempotencyRecord.objects.get().action_log)
        self.notification.assert_called_once_with(case.id)

    def test_report_specific_workflow_mapping_is_used(self):
        mapped = StateDefinition.objects.create(name="Mapped")
        StateStep.objects.create(
            name="Review", is_start_state=True, state_definition=mapped
        )
        CaseStateMapping.objects.create(
            report_type=self.report_type, state_definition=mapped
        )
        self.assertEqual(200, self._post().status_code)
        self.assertEqual(mapped, Case.objects.get().state_definition)

    def test_header_key_allows_empty_object(self):
        self.assertEqual(200, self._post({}, key="header-key").status_code)
        self.assertEqual("header-key", IntegrationIdempotencyRecord.objects.get().key)

    def test_oversized_header_key_returns_validation_error_and_is_audited(self):
        self._assert_rejected(self._post({}, key="k" * 201), 400, "invalid_payload")

    def test_promotion_notification_waits_for_transaction_commit(self):
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            response = self.client.post(
                self._url(),
                data='{"externalActionId":"deferred-notification"}',
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {self.token.token}",
            )
            self.assertEqual(200, response.status_code)
            self.notification.assert_not_called()
        self.assertEqual(1, len(callbacks))
        callbacks[0]()
        self.notification.assert_called_once_with(Case.objects.get().id)

    def test_retry_returns_original_response_without_repeating_promotion(self):
        first = self._post()
        second = self._post()
        self.assertEqual(200, second.status_code)
        self.assertEqual(first.json(), second.json())
        self.assertEqual(1, Case.objects.count())
        self.assertEqual(1, CaseState.objects.count())
        self.notification.assert_called_once()
        self.assertEqual(1, IntegrationIdempotencyRecord.objects.count())
        self.assertEqual(
            1,
            IntegrationActionLog.objects.filter(
                result_status=IntegrationActionLog.ResultStatus.REPLAYED
            ).count(),
        )

    def test_existing_case_is_returned_with_new_key_without_reopening_it(self):
        self._post()
        case = Case.objects.get()
        case.is_finished = True
        case.save(update_fields=["is_finished"])
        response = self._post({"externalActionId": "another-promotion"})
        self.assertEqual(200, response.status_code)
        self.assertTrue(response.json()["alreadyPromoted"])
        self.assertEqual(str(case.id), response.json()["case"]["id"])
        case.refresh_from_db()
        self.assertTrue(case.is_finished)
        self.assertEqual(1, Case.objects.count())
        self.notification.assert_called_once()

    def test_same_key_with_changed_payload_is_conflict(self):
        self._post(key="same-key")
        response = self._post({"externalActionId": "changed"}, key="same-key")
        self.assertEqual(409, response.status_code)
        self.assertEqual("idempotency_conflict", response.json()["error"]["code"])
        self.assertEqual(1, Case.objects.count())

    def test_same_key_cannot_target_another_report(self):
        self._post()
        other = self._report()
        response = self._post(report_id=other.id)
        self.assertEqual(409, response.status_code)
        self.assertEqual("idempotency_conflict", response.json()["error"]["code"])
        other.refresh_from_db()
        self.assertIsNone(other.case_id)
        self.assertEqual(1, Case.objects.count())

    def test_disabled_integration_client_is_denied(self):
        self.integration_client.status = IntegrationClient.Status.DISABLED
        self.integration_client.save(update_fields=["status"])
        response = self._post()
        self.assertEqual(403, response.status_code)
        self.assertEqual("integration_client_denied", response.json()["error"]["code"])
        self.assertFalse(Case.objects.exists())

    def test_other_scope_does_not_authorize_promotion(self):
        self.integration_client.scope_codes = [
            IntegrationScope.AI_CREATE_COMMENT,
            IntegrationScope.RISK_UPDATE,
        ]
        self.integration_client.save(update_fields=["scope_codes"])
        self._assert_rejected(self._post(), 403, "scope_denied")

    def test_human_bound_token_is_denied_even_for_superuser(self):
        self.reporter.is_superuser = True
        self.reporter.save(update_fields=["is_superuser"])
        self.token.user = self.reporter
        self.token.save(update_fields=["user"])
        self._assert_rejected(self._post(), 403, "service_identity_denied")

    def test_browser_session_does_not_replace_service_oauth(self):
        self.client.force_login(self.reporter)
        response = self.client.post(
            self._url(), data="{}", content_type="application/json"
        )
        self.assertEqual(401, response.status_code)
        self.assertEqual("oauth_required", response.json()["error"]["code"])
        self.assertFalse(Case.objects.exists())

    def test_expired_token_is_denied(self):
        self.token.expires = timezone.now() - timedelta(minutes=1)
        self.token.save(update_fields=["expires"])
        response = self._post()
        self.assertEqual(401, response.status_code)
        self.assertEqual("oauth_required", response.json()["error"]["code"])
        self.assertFalse(Case.objects.exists())

    def test_integration_policy_is_enforced(self):
        Configuration.objects.create(key=INTEGRATION_ENABLED_KEY, value="disable")
        self._assert_rejected(self._post(), 403, "integration_disabled")

    def test_ai_policy_is_enforced(self):
        Configuration.objects.create(key=AI_ENABLED_KEY, value="disable")
        self._assert_rejected(self._post(), 403, "ai_disabled")

    def test_policy_still_applies_to_replay(self):
        self._post()
        Configuration.objects.create(key=AI_ENABLED_KEY, value="disable")
        response = self._post()
        self.assertEqual(403, response.status_code)
        self.assertEqual("ai_disabled", response.json()["error"]["code"])
        self.assertEqual(1, Case.objects.count())

    def test_public_schema_is_denied(self):
        try:
            response = Client().post(
                self._url(),
                data="{}",
                content_type="application/json",
                HTTP_HOST="localhost",
            )
        finally:
            connection.set_tenant(self.tenant)
        self.assertEqual(403, response.status_code)
        self.assertEqual("tenant_denied", response.json()["error"]["code"])
        self.assertFalse(Case.objects.exists())

    def test_missing_report_is_not_found_and_audited(self):
        self._assert_rejected(self._post(report_id=uuid4()), 404, "report_not_found")

    def test_soft_deleted_report_is_not_found(self):
        self.report.delete()
        self._assert_rejected(self._post(), 404, "report_not_found")

    def test_token_and_report_are_isolated_to_the_selected_tenant(self):
        with schema_context("public"):
            other = Tenant(schema_name="promote_other", name="Other tenant")
            other.save(verbosity=0)
            Domain.objects.create(tenant=other, domain="promote-other.test")
        try:
            with tenant_context(other):
                authority = Authority.objects.create(code="OTHER", name="Other")
                reporter = AuthorityUser.objects.create(
                    username="other-reporter", authority=authority
                )
                report_type = ReportType.objects.create(
                    name="Other report",
                    category=Category.objects.create(name="other"),
                    definition={},
                )
                report = IncidentReport.objects.create(
                    reported_by=reporter,
                    report_type=report_type,
                    incident_date=timezone.now().date(),
                    data={},
                )
            # An existing foreign report is still absent in our tenant.
            self._assert_rejected(
                self._post(report_id=report.id), 404, "report_not_found"
            )
            # Our valid service token is unknown on the foreign tenant host.
            response = TenantClient(other).post(
                self._url(report.id),
                data='{"externalActionId":"other"}',
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {self.token.token}",
            )
            self.assertEqual(401, response.status_code)
            self.assertEqual("oauth_required", response.json()["error"]["code"])
            with tenant_context(other):
                report.refresh_from_db()
                self.assertIsNone(report.case_id)
                self.assertFalse(Case.objects.exists())
        finally:
            with schema_context("public"):
                # Resolve deferred report foreign keys before dropping test tables.
                with connection.cursor() as cursor:
                    cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
                other.delete(force_drop=True)
            connection.set_tenant(self.tenant)

    def test_invalid_payloads_do_not_mutate_or_claim_keys(self):
        for payload in [
            {},
            {"externalActionId": None},
            {"externalActionId": 1},
            {"externalActionId": " "},
            {"externalActionId": "a" * 201},
            {"externalActionId": "ok", "caseId": str(uuid4())},
        ]:
            with self.subTest(payload=payload):
                response = self._post(payload)
                self.assertEqual(400, response.status_code)
                self.assertEqual("invalid_payload", response.json()["error"]["code"])
        self.assertFalse(Case.objects.exists())
        self.assertFalse(IntegrationIdempotencyRecord.objects.exists())

    def test_invalid_json_is_audited_without_storing_raw_secret(self):
        for raw in ['{"token":"private-secret",', "[]"]:
            with self.subTest(raw=raw):
                response = self.client.post(
                    self._url(),
                    data=raw,
                    content_type="application/json",
                    HTTP_AUTHORIZATION=f"Bearer {self.token.token}",
                )
                self.assertEqual(400, response.status_code)
                self.assertEqual("invalid_json", response.json()["error"]["code"])
        for action in IntegrationActionLog.objects.all():
            self.assertNotIn("private-secret", json.dumps(action.result_summary))
            self.assertTrue(action.payload_hash)
        self.assertFalse(Case.objects.exists())

    def test_missing_workflow_is_conflict_and_key_can_be_retried_after_configuration(
        self,
    ):
        self.definition.is_default = False
        self.definition.save(update_fields=["is_default"])
        self._assert_rejected(self._post(), 409, "case_workflow_unavailable")
        self.definition.is_default = True
        self.definition.save(update_fields=["is_default"])
        self.assertEqual(200, self._post().status_code)

    def test_workflow_without_start_state_is_conflict(self):
        self.start.delete()
        self._assert_rejected(self._post(), 409, "case_workflow_unavailable")

    def test_failure_after_case_creation_rolls_back_case_state_report_and_key(self):
        with patch(
            "integrations.views._create_action_log",
            side_effect=RuntimeError("audit unavailable"),
        ):
            with self.assertRaisesMessage(RuntimeError, "audit unavailable"):
                self._post()
        self.report.refresh_from_db()
        self.assertIsNone(self.report.case_id)
        self.assertFalse(Case.objects.exists())
        self.assertFalse(CaseState.objects.exists())
        self.assertFalse(IntegrationIdempotencyRecord.objects.exists())
        self.notification.assert_not_called()

    def test_endpoint_only_accepts_post(self):
        self.assertEqual(405, self.client.get(self._url()).status_code)
