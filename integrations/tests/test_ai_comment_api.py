import json
from datetime import timedelta

from django.db import connection
from django.test import Client
from django.urls import resolve
from django.utils import timezone
from django_tenants.test.cases import TenantTestCase
from django_tenants.test.client import TenantClient
from oauth2_provider.models import get_access_token_model, get_application_model

from accounts.models import Authority, AuthorityUser
from integrations.constants import IntegrationScope
from integrations.models import (
    IntegrationActionLog,
    IntegrationClient,
    IntegrationIdempotencyRecord,
    IntegrationReportComment,
)
from reports.models import Category, IncidentReport, ReportType
from threads.models import Comment


class AICommentApiTests(TenantTestCase):
    @classmethod
    def setup_tenant(cls, tenant):
        tenant.name = "Tenant Alpha"

    def setUp(self):
        connection.set_tenant(self.tenant)
        self.client = TenantClient(self.tenant)
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
            data={"symptom": "sudden death", "token": "private-report-input"},
            reported_by=self.reporter,
            incident_date=timezone.datetime(2026, 6, 2).date(),
            report_type=self.report_type,
        )
        self.report.relevant_authorities.add(self.authority)
        self.application, self.integration_client, self.access_token = (
            self._create_oauth_client(
                "ai-client",
                scope_codes=[IntegrationScope.AI_CREATE_COMMENT],
                token="ai-comment-token",
            )
        )

    def test_endpoint_is_exposed_at_versioned_report_comments_path(self):
        match = resolve(self._url())

        self.assertEqual("integration-report-comments", match.url_name)

    def test_create_comment_stores_integration_owned_comment_without_thread_comment(self):
        payload = {
            "externalActionId": "ai-action-001",
            "body": "AI assessment: unusual mortality pattern. Recommend officer review.",
            "visibility": "staff",
            "metadata": {
                "model": "external-ai-v1",
                "clientSecret": "plain-secret",
            },
            "recommendation": {
                "type": "officer_review",
                "confidence": 0.82,
                "headers": [{"name": "X-Api-Key", "value": "plain-key"}],
            },
        }

        response = self._post_comment(
            payload,
            idempotency_key="idem-create-001",
        )

        self.assertEqual(202, response.status_code)
        response_payload = response.json()
        self.assertEqual("2026-06-02", response_payload["schemaVersion"])
        self.assertEqual("accepted", response_payload["status"])
        self.assertEqual(str(self.report.id), response_payload["comment"]["reportId"])
        self.assertEqual("staff", response_payload["comment"]["visibility"])
        self.assertEqual(
            "ai-action-001",
            response_payload["comment"]["externalActionId"],
        )
        self.assertTrue(response_payload["recommendationStored"])

        stored_comment = IntegrationReportComment.objects.get()
        self.assertEqual(self.report, stored_comment.report)
        self.assertEqual(self.integration_client, stored_comment.integration_client)
        self.assertEqual(payload["body"], stored_comment.body)
        self.assertEqual(
            {"model": "external-ai-v1", "clientSecret": "[REDACTED]"},
            stored_comment.metadata,
        )
        self.assertEqual(
            {
                "type": "officer_review",
                "confidence": 0.82,
                "headers": [{"name": "X-Api-Key", "value": "[REDACTED]"}],
            },
            stored_comment.recommendation,
        )
        self.assertEqual(0, Comment.objects.count())

        action_log = IntegrationActionLog.objects.get(
            result_status=IntegrationActionLog.ResultStatus.ACCEPTED
        )
        self.assertEqual("ai.create_comment", action_log.action_type)
        self.assertEqual(IntegrationScope.AI_CREATE_COMMENT, action_log.required_scope)
        self.assertEqual("reports.IncidentReport", action_log.target_type)
        self.assertEqual(str(self.report.id), action_log.target_id)
        self.assertEqual("idem-create-001", action_log.idempotency_key)
        self.assertEqual("ai-action-001", action_log.external_action_id)
        self.assertEqual("[REDACTED]", action_log.request_headers_summary["Authorization"])
        self.assertEqual(
            "[REDACTED]",
            action_log.result_summary["payloadSummary"]["metadata"]["clientSecret"],
        )

        idempotency = IntegrationIdempotencyRecord.objects.get()
        self.assertEqual(action_log, idempotency.action_log)
        self.assertEqual(202, idempotency.response_status_code)
        self.assertEqual(response_payload, idempotency.response_summary)

    def test_external_action_id_can_supply_idempotency_key(self):
        response = self._post_comment(
            {
                "externalActionId": "external-action-key",
                "body": "AI recommendation persisted from external action id.",
            }
        )

        self.assertEqual(202, response.status_code)
        idempotency = IntegrationIdempotencyRecord.objects.get()
        self.assertEqual("external-action-key", idempotency.key)

    def test_same_idempotency_key_and_payload_replays_same_response(self):
        payload = {
            "externalActionId": "ai-replay-001",
            "body": "Replay this exact accepted response.",
        }
        first = self._post_comment(payload, idempotency_key="idem-replay-001")
        second = self._post_comment(payload, idempotency_key="idem-replay-001")

        self.assertEqual(202, first.status_code)
        self.assertEqual(202, second.status_code)
        self.assertEqual(first.json(), second.json())
        self.assertEqual(1, IntegrationReportComment.objects.count())
        self.assertEqual(1, IntegrationIdempotencyRecord.objects.count())
        self.assertEqual(
            1,
            IntegrationActionLog.objects.filter(
                result_status=IntegrationActionLog.ResultStatus.ACCEPTED
            ).count(),
        )
        self.assertEqual(
            1,
            IntegrationActionLog.objects.filter(
                result_status=IntegrationActionLog.ResultStatus.REPLAYED
            ).count(),
        )

    def test_same_idempotency_key_and_payload_for_different_report_conflicts(self):
        second_report = IncidentReport.objects.create(
            data={"symptom": "same body different report"},
            reported_by=self.reporter,
            incident_date=timezone.datetime(2026, 6, 2).date(),
            report_type=self.report_type,
        )
        second_report.relevant_authorities.add(self.authority)
        payload = {
            "externalActionId": "ai-target-aware-001",
            "body": "Same request body must not replay across report targets.",
        }

        first = self._post_comment(payload, idempotency_key="idem-target-aware")
        second = self._post_comment(
            payload,
            idempotency_key="idem-target-aware",
            url=f"/api/integrations/v1/reports/{second_report.id}/comments",
        )

        self.assertEqual(202, first.status_code)
        self.assertEqual(409, second.status_code)
        self.assertEqual(
            "idempotency_conflict",
            second.json()["error"]["code"],
        )
        self.assertEqual(1, IntegrationReportComment.objects.count())
        self.assertEqual(
            self.report,
            IntegrationReportComment.objects.get().report,
        )
        idempotency = IntegrationIdempotencyRecord.objects.get()
        self.assertEqual(str(self.report.id), idempotency.target_id)
        rejected_log = IntegrationActionLog.objects.get(
            result_status=IntegrationActionLog.ResultStatus.REJECTED,
            result_summary__error__code="idempotency_conflict",
        )
        self.assertEqual(str(second_report.id), rejected_log.target_id)

    def test_same_idempotency_key_with_different_payload_conflicts(self):
        first = self._post_comment(
            {
                "externalActionId": "ai-conflict-001",
                "body": "Original comment.",
            },
            idempotency_key="idem-conflict-001",
        )
        second = self._post_comment(
            {
                "externalActionId": "ai-conflict-002",
                "body": "Changed comment.",
            },
            idempotency_key="idem-conflict-001",
        )

        self.assertEqual(202, first.status_code)
        self.assertEqual(409, second.status_code)
        self.assertEqual(
            "idempotency_conflict",
            second.json()["error"]["code"],
        )
        self.assertEqual(1, IntegrationReportComment.objects.count())
        rejected_log = IntegrationActionLog.objects.get(
            result_status=IntegrationActionLog.ResultStatus.REJECTED,
            result_summary__error__code="idempotency_conflict",
        )
        self.assertEqual("idem-conflict-001", rejected_log.idempotency_key)

    def test_missing_functional_scope_is_denied_and_audited(self):
        _application, _integration_client, access_token = self._create_oauth_client(
            "ai-no-comment-scope",
            scope_codes=[],
            token="ai-no-comment-scope-token",
        )

        response = self._post_comment(
            {
                "externalActionId": "ai-no-scope",
                "body": "Should not be accepted.",
            },
            idempotency_key="idem-no-scope",
            token=access_token.token,
        )

        self.assertEqual(403, response.status_code)
        self.assertEqual("scope_denied", response.json()["error"]["code"])
        self.assertEqual(0, IntegrationReportComment.objects.count())
        action_log = IntegrationActionLog.objects.get()
        self.assertEqual(
            IntegrationActionLog.ResultStatus.REJECTED,
            action_log.result_status,
        )
        self.assertEqual("scope_denied", action_log.result_summary["error"]["code"])

    def test_user_bound_oauth_token_is_denied_even_for_valid_service_application(self):
        _application, _integration_client, access_token = self._create_oauth_client(
            "ai-human-token",
            scope_codes=[IntegrationScope.AI_CREATE_COMMENT],
            token="ai-human-token",
            token_user=self.reporter,
        )

        response = self._post_comment(
            {
                "externalActionId": "ai-human-token",
                "body": "Human-bound OAuth tokens cannot write integration comments.",
            },
            idempotency_key="idem-human-token",
            token=access_token.token,
        )

        self.assertEqual(403, response.status_code)
        self.assertEqual("service_identity_denied", response.json()["error"]["code"])
        self.assertEqual(0, IntegrationReportComment.objects.count())
        action_log = IntegrationActionLog.objects.get()
        self.assertEqual(
            IntegrationActionLog.ResultStatus.REJECTED,
            action_log.result_status,
        )
        self.assertEqual(
            "service_identity_denied",
            action_log.result_summary["error"]["code"],
        )

    def test_missing_bearer_token_is_not_accepted_as_browser_or_cookie_auth(self):
        response = self.client.post(
            self._url(),
            data=json.dumps(
                {
                    "externalActionId": "ai-no-token",
                    "body": "Should require OAuth.",
                }
            ),
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY="idem-no-token",
        )

        self.assertEqual(401, response.status_code)
        self.assertEqual("oauth_required", response.json()["error"]["code"])
        self.assertEqual(0, IntegrationReportComment.objects.count())
        self.assertEqual(0, IntegrationActionLog.objects.count())

    def test_public_schema_is_denied_before_integration_authorization(self):
        public_client = Client()
        try:
            response = public_client.post(
                self._url(),
                data=json.dumps(
                    {
                        "externalActionId": "ai-public",
                        "body": "Should be denied before token lookup.",
                    }
                ),
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {self.access_token.token}",
                HTTP_IDEMPOTENCY_KEY="idem-public",
            )
        finally:
            connection.set_tenant(self.tenant)

        self.assertEqual(403, response.status_code)
        self.assertEqual("tenant_denied", response.json()["error"]["code"])
        self.assertEqual(0, IntegrationReportComment.objects.count())
        self.assertEqual(0, IntegrationActionLog.objects.count())

    def test_invalid_payload_is_rejected_and_audited(self):
        response = self._post_comment(
            {
                "externalActionId": "ai-invalid",
                "body": "Valid body but unsupported field.",
                "clusterId": "not-in-i4",
            },
            idempotency_key="idem-invalid",
        )

        self.assertEqual(400, response.status_code)
        self.assertEqual("invalid_payload", response.json()["error"]["code"])
        self.assertEqual(0, IntegrationReportComment.objects.count())
        action_log = IntegrationActionLog.objects.get()
        self.assertEqual(
            IntegrationActionLog.ResultStatus.REJECTED,
            action_log.result_status,
        )
        self.assertEqual("invalid_payload", action_log.result_summary["error"]["code"])

    def test_falsey_non_string_external_action_id_is_rejected_when_present(self):
        invalid_values = [0, False, {}, []]

        for index, value in enumerate(invalid_values, start=1):
            with self.subTest(value=value):
                response = self._post_comment(
                    {
                        "externalActionId": value,
                        "body": "Header idempotency does not hide bad action ids.",
                    },
                    idempotency_key=f"idem-bad-external-action-{index}",
                )

                self.assertEqual(400, response.status_code)
                self.assertEqual("invalid_payload", response.json()["error"]["code"])

        self.assertEqual(0, IntegrationReportComment.objects.count())
        self.assertEqual(len(invalid_values), IntegrationActionLog.objects.count())

    def test_invalid_comment_payload_shapes_are_rejected(self):
        invalid_payloads = [
            {},
            {"body": ""},
            {"body": "Has body", "visibility": "public"},
            {"body": "Has body", "metadata": []},
            {"body": "Has body", "recommendation": []},
        ]

        for index, payload in enumerate(invalid_payloads, start=1):
            with self.subTest(payload=payload):
                response = self._post_comment(
                    payload,
                    idempotency_key=f"idem-invalid-shape-{index}",
                )

                self.assertEqual(400, response.status_code)
                self.assertEqual("invalid_payload", response.json()["error"]["code"])

        self.assertEqual(0, IntegrationReportComment.objects.count())
        self.assertEqual(len(invalid_payloads), IntegrationActionLog.objects.count())

    def test_missing_report_is_rejected_and_audited(self):
        missing_report_id = "11111111-1111-1111-1111-111111111111"
        response = self._post_comment(
            {
                "externalActionId": "ai-missing-report",
                "body": "No report target exists.",
            },
            idempotency_key="idem-missing-report",
            url=f"/api/integrations/v1/reports/{missing_report_id}/comments",
        )

        self.assertEqual(404, response.status_code)
        self.assertEqual("report_not_found", response.json()["error"]["code"])
        self.assertEqual(0, IntegrationReportComment.objects.count())
        action_log = IntegrationActionLog.objects.get()
        self.assertEqual(missing_report_id, action_log.target_id)
        self.assertEqual("report_not_found", action_log.result_summary["error"]["code"])

    def _create_oauth_client(self, code, scope_codes, token, token_user=None):
        application_model = get_application_model()
        application = application_model.objects.create(
            name=code,
            user=None,
            client_type=application_model.CLIENT_CONFIDENTIAL,
            authorization_grant_type=application_model.GRANT_CLIENT_CREDENTIALS,
        )
        integration_client = IntegrationClient.objects.create(
            name=code,
            code=code,
            integration_type=IntegrationClient.IntegrationType.AI_ASSISTANT,
            oauth_application=application,
            scope_codes=scope_codes,
        )
        access_token_model = get_access_token_model()
        access_token = access_token_model.objects.create(
            user=token_user,
            token=token,
            application=application,
            expires=timezone.now() + timedelta(hours=1),
            scope="",
        )
        return application, integration_client, access_token

    def _post_comment(
        self,
        payload,
        idempotency_key=None,
        token=None,
        url=None,
    ):
        headers = {
            "HTTP_AUTHORIZATION": f"Bearer {token or self.access_token.token}",
        }
        if idempotency_key:
            headers["HTTP_IDEMPOTENCY_KEY"] = idempotency_key

        return self.client.post(
            url or self._url(),
            data=json.dumps(payload),
            content_type="application/json",
            **headers,
        )

    def _url(self):
        return f"/api/integrations/v1/reports/{self.report.id}/comments"
