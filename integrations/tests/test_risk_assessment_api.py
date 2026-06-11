import json
from datetime import timedelta

from django.db import connection
from django.test import Client
from django.urls import Resolver404, resolve
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
    RiskAssessment,
)
from reports.models import Category, IncidentReport, ReportType


class RiskAssessmentApiTests(TenantTestCase):
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
                "risk-client",
                scope_codes=[IntegrationScope.RISK_UPDATE],
                token="risk-update-token",
            )
        )

    def test_endpoints_are_exposed_at_versioned_risk_assessment_paths(self):
        report_match = resolve(self._report_url())

        self.assertEqual(
            "integration-report-risk-assessments",
            report_match.url_name,
        )

        with self.assertRaises(Resolver404):
            resolve(self._case_url())

    def test_create_report_risk_assessment_stores_current_projection_and_audit(self):
        payload = {
            "externalAssessmentId": "risk-assessment-001",
            "level": "HIGH",
            "score": 0.84,
            "factors": [
                {"key": "mortality_count", "weight": 0.5},
                {"name": "X-Api-Key", "value": "plain-key"},
            ],
            "evaluatorVersion": "risk-evaluator-v1",
        }

        response = self._post_report_risk(
            payload,
            idempotency_key="idem-risk-create-001",
        )

        self.assertEqual(202, response.status_code)
        response_payload = response.json()
        self.assertEqual("2026-06-02", response_payload["schemaVersion"])
        self.assertEqual("accepted", response_payload["status"])
        risk_payload = response_payload["riskAssessment"]
        self.assertEqual("report", risk_payload["target"]["type"])
        self.assertEqual(str(self.report.id), risk_payload["target"]["id"])
        self.assertEqual("HIGH", risk_payload["level"])
        self.assertEqual(0.84, risk_payload["score"])
        self.assertTrue(risk_payload["isCurrent"])
        self.assertEqual(
            "risk-assessment-001",
            risk_payload["externalAssessmentId"],
        )
        self.assertEqual(0, risk_payload["replacedCurrentCount"])

        stored_assessment = RiskAssessment.objects.get()
        self.assertEqual(RiskAssessment.TargetType.REPORT, stored_assessment.target_type)
        self.assertEqual(str(self.report.id), stored_assessment.target_id)
        self.assertEqual(RiskAssessment.Level.HIGH, stored_assessment.level)
        self.assertEqual(0.84, float(stored_assessment.score))
        self.assertEqual(
            RiskAssessment.Source.EXTERNAL_RISK_EVALUATOR,
            stored_assessment.source,
        )
        self.assertEqual(
            [
                {"key": "mortality_count", "weight": 0.5},
                {"name": "X-Api-Key", "value": "[REDACTED]"},
            ],
            stored_assessment.factors,
        )
        self.assertEqual(self.integration_client, stored_assessment.integration_client)

        action_log = IntegrationActionLog.objects.get(
            result_status=IntegrationActionLog.ResultStatus.ACCEPTED
        )
        self.assertEqual("risk.update", action_log.action_type)
        self.assertEqual(IntegrationScope.RISK_UPDATE, action_log.required_scope)
        self.assertEqual("reports.IncidentReport", action_log.target_type)
        self.assertEqual(str(self.report.id), action_log.target_id)
        self.assertEqual("idem-risk-create-001", action_log.idempotency_key)
        self.assertEqual("risk-assessment-001", action_log.external_action_id)
        self.assertEqual("[REDACTED]", action_log.request_headers_summary["Authorization"])
        self.assertEqual(
            "[REDACTED]",
            action_log.result_summary["payloadSummary"]["factors"][1]["value"],
        )

        idempotency = IntegrationIdempotencyRecord.objects.get()
        self.assertEqual(action_log, idempotency.action_log)
        self.assertEqual(202, idempotency.response_status_code)
        self.assertEqual(response_payload, idempotency.response_summary)

    def test_create_report_risk_assessment_replaces_current_projection(self):
        first = self._post_report_risk(
            {
                "externalAssessmentId": "risk-report-current-001",
                "level": "LOW",
                "score": 0.25,
            },
            idempotency_key="idem-report-current-001",
        )
        second = self._post_report_risk(
            {
                "externalAssessmentId": "risk-report-current-002",
                "level": "HIGH",
                "score": 0.8,
            },
            idempotency_key="idem-report-current-002",
        )

        self.assertEqual(202, first.status_code)
        self.assertEqual(202, second.status_code)
        self.assertEqual(
            1,
            second.json()["riskAssessment"]["replacedCurrentCount"],
        )
        first_assessment = RiskAssessment.objects.get(
            external_assessment_id="risk-report-current-001"
        )
        second_assessment = RiskAssessment.objects.get(
            external_assessment_id="risk-report-current-002"
        )
        self.assertFalse(first_assessment.is_current)
        self.assertTrue(second_assessment.is_current)
        self.assertEqual(RiskAssessment.TargetType.REPORT, second_assessment.target_type)
        self.assertEqual(str(self.report.id), second_assessment.target_id)

    def test_external_assessment_id_can_supply_idempotency_key(self):
        response = self._post_report_risk(
            {
                "externalAssessmentId": "risk-idempotency-body-key",
                "level": "MEDIUM",
            }
        )

        self.assertEqual(202, response.status_code)
        idempotency = IntegrationIdempotencyRecord.objects.get()
        self.assertEqual("risk-idempotency-body-key", idempotency.key)

    def test_same_idempotency_key_and_payload_replays_same_assessment(self):
        payload = {
            "externalAssessmentId": "risk-replay-001",
            "level": "HIGH",
            "score": 0.7,
        }

        first = self._post_report_risk(payload, idempotency_key="idem-risk-replay")
        second = self._post_report_risk(payload, idempotency_key="idem-risk-replay")

        self.assertEqual(202, first.status_code)
        self.assertEqual(202, second.status_code)
        self.assertEqual("accepted", first.json()["status"])
        self.assertEqual("replayed", second.json()["status"])
        self.assertEqual(
            first.json()["riskAssessment"],
            second.json()["riskAssessment"],
        )
        self.assertEqual(1, RiskAssessment.objects.count())
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

    def test_same_idempotency_key_replays_after_target_is_soft_deleted(self):
        payload = {
            "externalAssessmentId": "risk-replay-deleted-target",
            "level": "HIGH",
            "score": 0.72,
        }
        first = self._post_report_risk(
            payload,
            idempotency_key="idem-risk-replay-deleted-target",
        )

        self.report.delete()
        second = self._post_report_risk(
            payload,
            idempotency_key="idem-risk-replay-deleted-target",
        )

        self.assertEqual(202, first.status_code)
        self.assertEqual(202, second.status_code)
        self.assertEqual("replayed", second.json()["status"])
        self.assertEqual(
            first.json()["riskAssessment"],
            second.json()["riskAssessment"],
        )
        self.assertEqual(1, RiskAssessment.objects.count())
        self.assertEqual(1, IntegrationIdempotencyRecord.objects.count())
        self.assertEqual(
            1,
            IntegrationActionLog.objects.filter(
                result_status=IntegrationActionLog.ResultStatus.REPLAYED
            ).count(),
        )

    def test_same_idempotency_key_and_payload_for_different_report_conflicts(self):
        second_report = IncidentReport.objects.create(
            data={"symptom": "same risk body different report"},
            reported_by=self.reporter,
            incident_date=timezone.datetime(2026, 6, 2).date(),
            report_type=self.report_type,
        )
        second_report.relevant_authorities.add(self.authority)
        payload = {
            "externalAssessmentId": "risk-target-aware-001",
            "level": "LOW",
        }

        first = self._post_report_risk(payload, idempotency_key="idem-risk-target")
        second = self._post_report_risk(
            payload,
            idempotency_key="idem-risk-target",
            url=f"/api/integrations/v1/reports/{second_report.id}/risk-assessments",
        )

        self.assertEqual(202, first.status_code)
        self.assertEqual(409, second.status_code)
        self.assertEqual(
            "idempotency_conflict",
            second.json()["error"]["code"],
        )
        self.assertEqual(1, RiskAssessment.objects.count())
        idempotency = IntegrationIdempotencyRecord.objects.get()
        self.assertEqual(str(self.report.id), idempotency.target_id)
        rejected_log = IntegrationActionLog.objects.get(
            result_status=IntegrationActionLog.ResultStatus.REJECTED,
            result_summary__error__code="idempotency_conflict",
        )
        self.assertEqual(str(second_report.id), rejected_log.target_id)

    def test_same_idempotency_key_for_different_missing_report_conflicts_before_404(self):
        missing_report_id = "33333333-3333-3333-3333-333333333333"
        payload = {
            "externalAssessmentId": "risk-missing-target-conflict",
            "level": "LOW",
        }

        first = self._post_report_risk(
            payload,
            idempotency_key="idem-risk-missing-target-conflict",
        )
        second = self._post_report_risk(
            payload,
            idempotency_key="idem-risk-missing-target-conflict",
            url=f"/api/integrations/v1/reports/{missing_report_id}/risk-assessments",
        )

        self.assertEqual(202, first.status_code)
        self.assertEqual(409, second.status_code)
        self.assertEqual(
            "idempotency_conflict",
            second.json()["error"]["code"],
        )
        self.assertEqual(1, RiskAssessment.objects.count())
        self.assertEqual(1, IntegrationIdempotencyRecord.objects.count())
        rejected_log = IntegrationActionLog.objects.get(
            result_status=IntegrationActionLog.ResultStatus.REJECTED,
            result_summary__error__code="idempotency_conflict",
        )
        self.assertEqual(missing_report_id, rejected_log.target_id)

    def test_same_idempotency_key_with_different_payload_conflicts(self):
        first = self._post_report_risk(
            {
                "externalAssessmentId": "risk-conflict-001",
                "level": "MEDIUM",
            },
            idempotency_key="idem-risk-conflict",
        )
        second = self._post_report_risk(
            {
                "externalAssessmentId": "risk-conflict-002",
                "level": "CRITICAL",
            },
            idempotency_key="idem-risk-conflict",
        )

        self.assertEqual(202, first.status_code)
        self.assertEqual(409, second.status_code)
        self.assertEqual(
            "idempotency_conflict",
            second.json()["error"]["code"],
        )
        self.assertEqual(1, RiskAssessment.objects.count())

    def test_missing_functional_scope_is_denied_and_audited(self):
        _application, _integration_client, access_token = self._create_oauth_client(
            "risk-no-scope",
            scope_codes=[],
            token="risk-no-scope-token",
        )

        response = self._post_report_risk(
            {
                "externalAssessmentId": "risk-no-scope",
                "level": "HIGH",
            },
            idempotency_key="idem-risk-no-scope",
            token=access_token.token,
        )

        self.assertEqual(403, response.status_code)
        self.assertEqual("scope_denied", response.json()["error"]["code"])
        self.assertEqual(0, RiskAssessment.objects.count())
        action_log = IntegrationActionLog.objects.get()
        self.assertEqual(
            IntegrationActionLog.ResultStatus.REJECTED,
            action_log.result_status,
        )
        self.assertEqual("scope_denied", action_log.result_summary["error"]["code"])

    def test_user_bound_oauth_token_is_denied_even_for_valid_service_application(self):
        _application, _integration_client, access_token = self._create_oauth_client(
            "risk-human-token",
            scope_codes=[IntegrationScope.RISK_UPDATE],
            token="risk-human-token",
            token_user=self.reporter,
        )

        response = self._post_report_risk(
            {
                "externalAssessmentId": "risk-human-token",
                "level": "HIGH",
            },
            idempotency_key="idem-risk-human-token",
            token=access_token.token,
        )

        self.assertEqual(403, response.status_code)
        self.assertEqual("service_identity_denied", response.json()["error"]["code"])
        self.assertEqual(0, RiskAssessment.objects.count())
        action_log = IntegrationActionLog.objects.get()
        self.assertEqual(
            "service_identity_denied",
            action_log.result_summary["error"]["code"],
        )

    def test_missing_bearer_token_is_not_accepted_as_browser_or_cookie_auth(self):
        response = self.client.post(
            self._report_url(),
            data=json.dumps(
                {
                    "externalAssessmentId": "risk-no-token",
                    "level": "HIGH",
                }
            ),
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY="idem-risk-no-token",
        )

        self.assertEqual(401, response.status_code)
        self.assertEqual("oauth_required", response.json()["error"]["code"])
        self.assertEqual(0, RiskAssessment.objects.count())
        self.assertEqual(0, IntegrationActionLog.objects.count())

    def test_public_schema_is_denied_before_integration_authorization(self):
        public_client = Client()
        try:
            response = public_client.post(
                self._report_url(),
                data=json.dumps(
                    {
                        "externalAssessmentId": "risk-public",
                        "level": "HIGH",
                    }
                ),
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {self.access_token.token}",
                HTTP_IDEMPOTENCY_KEY="idem-risk-public",
            )
        finally:
            connection.set_tenant(self.tenant)

        self.assertEqual(403, response.status_code)
        self.assertEqual("tenant_denied", response.json()["error"]["code"])
        self.assertEqual(0, RiskAssessment.objects.count())
        self.assertEqual(0, IntegrationActionLog.objects.count())

    def test_invalid_risk_payload_shapes_are_rejected_and_audited(self):
        invalid_payloads = [
            {},
            {"level": "SEVERE"},
            {"level": "HIGH", "score": True},
            {"level": "HIGH", "score": "0.5"},
            {"level": "HIGH", "score": 1.1},
            {"level": "HIGH", "factors": "not-json-object-or-array"},
            {"level": "HIGH", "evaluatorVersion": 1},
            {"level": "HIGH", "externalAssessmentId": 0},
            {"level": "HIGH", "source": "human"},
            {"level": "HIGH", "source": []},
            {"level": "HIGH", "source": {"kind": "ai"}},
            {"level": "HIGH", "target": {"type": "cluster"}},
        ]

        for index, payload in enumerate(invalid_payloads, start=1):
            with self.subTest(payload=payload):
                response = self._post_report_risk(
                    payload,
                    idempotency_key=f"idem-invalid-risk-{index}",
                )

                self.assertEqual(400, response.status_code)
                self.assertEqual("invalid_payload", response.json()["error"]["code"])

        self.assertEqual(0, RiskAssessment.objects.count())
        self.assertEqual(len(invalid_payloads), IntegrationActionLog.objects.count())

    def test_missing_targets_are_rejected_and_audited(self):
        missing_report_id = "11111111-1111-1111-1111-111111111111"

        report_response = self._post_report_risk(
            {
                "externalAssessmentId": "risk-missing-report",
                "level": "HIGH",
            },
            idempotency_key="idem-risk-missing-report",
            url=f"/api/integrations/v1/reports/{missing_report_id}/risk-assessments",
        )

        self.assertEqual(404, report_response.status_code)
        self.assertEqual("report_not_found", report_response.json()["error"]["code"])
        self.assertEqual(0, RiskAssessment.objects.count())
        self.assertEqual(
            {missing_report_id},
            set(IntegrationActionLog.objects.values_list("target_id", flat=True)),
        )
        self.assertEqual(0, IntegrationIdempotencyRecord.objects.count())

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
            integration_type=IntegrationClient.IntegrationType.RISK_EVALUATOR,
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

    def _post_report_risk(
        self,
        payload,
        idempotency_key=None,
        token=None,
        url=None,
    ):
        return self._post_risk(
            url=url or self._report_url(),
            payload=payload,
            idempotency_key=idempotency_key,
            token=token,
        )

    def _post_risk(
        self,
        *,
        url,
        payload,
        idempotency_key=None,
        token=None,
    ):
        headers = {
            "HTTP_AUTHORIZATION": f"Bearer {token or self.access_token.token}",
        }
        if idempotency_key:
            headers["HTTP_IDEMPOTENCY_KEY"] = idempotency_key

        return self.client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json",
            **headers,
        )

    def _report_url(self):
        return f"/api/integrations/v1/reports/{self.report.id}/risk-assessments"

    def _case_url(self):
        return (
            "/api/integrations/v1/cases/"
            "22222222-2222-2222-2222-222222222222/risk-assessments"
        )
