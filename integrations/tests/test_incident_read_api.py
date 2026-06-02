from datetime import timedelta
from decimal import Decimal

from django.contrib.gis.geos import Point
from django.db import connection
from django.test import Client
from django.urls import resolve
from django.utils import timezone
from django_tenants.test.cases import TenantTestCase
from django_tenants.test.client import TenantClient
from oauth2_provider.models import get_access_token_model, get_application_model

from accounts.models import Authority, AuthorityUser
from integrations.constants import IntegrationScope
from integrations.models import IntegrationActionLog, IntegrationClient, RiskAssessment
from integrations.services import create_risk_assessment
from reports.models import Category, IncidentReport, ReportType


class IncidentReadApiTests(TenantTestCase):
    @classmethod
    def setup_tenant(cls, tenant):
        tenant.name = "Tenant Alpha"

    def setUp(self):
        connection.set_tenant(self.tenant)
        self.client = TenantClient(self.tenant)
        self.parent_authority = Authority.objects.create(code="BKK", name="Bangkok")
        self.child_authority = Authority.objects.create(code="JJ", name="Jatujak")
        self.child_authority.inherits.add(self.parent_authority)
        self.sibling_authority = Authority.objects.create(code="CM", name="Chiangmai")
        self.reporter = AuthorityUser.objects.create(
            username="reporter",
            authority=self.child_authority,
        )
        self.category = Category.objects.create(name="animal")
        self.report_type = ReportType.objects.create(
            name="Animal Sick/Death",
            category=self.category,
            definition={},
            published=True,
        )
        self.other_report_type = ReportType.objects.create(
            name="Other Incident",
            category=self.category,
            definition={},
            published=True,
        )
        self.report_type.authorities.add(self.parent_authority)
        self.other_report_type.authorities.add(self.sibling_authority)
        self.report = self._create_report(
            "parent-report",
            self.parent_authority,
            incident_date=timezone.datetime(2026, 6, 2).date(),
            gps_location=Point(101.003, 13.233),
            case_id="11111111-1111-1111-1111-111111111111",
        )
        self.child_report = self._create_report(
            "child-report",
            self.child_authority,
            incident_date=timezone.datetime(2026, 6, 3).date(),
        )
        self.sibling_report = self._create_report(
            "sibling-report",
            self.sibling_authority,
            incident_date=timezone.datetime(2026, 6, 4).date(),
            report_type=self.other_report_type,
        )
        self.test_report = self._create_report(
            "test-report",
            self.parent_authority,
            incident_date=timezone.datetime(2026, 6, 5).date(),
            test_flag=True,
        )
        self.old_report = self._create_report(
            "old-report",
            self.parent_authority,
            incident_date=timezone.datetime(2026, 5, 1).date(),
        )
        self.application, self.integration_client, self.access_token = (
            self._create_oauth_client(
                "incident-client",
                scope_codes=[IntegrationScope.INCIDENT_READ],
                token="incident-read-token",
            )
        )
        _risk_application, risk_client, _risk_token = self._create_oauth_client(
            "risk-for-incident-read",
            scope_codes=[IntegrationScope.RISK_UPDATE],
            token="risk-for-incident-read-token",
            integration_type=IntegrationClient.IntegrationType.RISK_EVALUATOR,
        )
        create_risk_assessment(
            target_type=RiskAssessment.TargetType.REPORT,
            target_id=self.report.id,
            level=RiskAssessment.Level.HIGH,
            score=Decimal("0.8400"),
            factors=[],
            source=RiskAssessment.Source.EXTERNAL_RISK_EVALUATOR,
            evaluator_version="risk-evaluator-v1",
            integration_client=risk_client,
            external_assessment_id="risk-report-001",
        )

    def test_endpoints_are_exposed_at_versioned_incident_paths(self):
        list_match = resolve("/api/integrations/v1/incidents")
        detail_match = resolve(f"/api/integrations/v1/incidents/{self.report.id}")

        self.assertEqual("integration-incidents", list_match.url_name)
        self.assertEqual("integration-incident-detail", detail_match.url_name)

    def test_read_incident_detail_returns_thin_payload_and_audits(self):
        response = self._get_detail()

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual("2026-06-02", payload["schemaVersion"])
        incident = payload["incident"]
        self.assertEqual(str(self.report.id), incident["id"])
        self.assertIn("createdAt", incident)
        self.assertIn("updatedAt", incident)
        self.assertEqual("2026-06-02", incident["incidentDate"])
        self.assertFalse(incident["testFlag"])
        self.assertEqual(
            {
                "id": str(self.report_type.id),
                "name": "Animal Sick/Death",
                "category": "animal",
            },
            incident["reportType"],
        )
        self.assertEqual([self.parent_authority.id], incident["relevantAuthorityIds"])
        self.assertEqual("11111111-1111-1111-1111-111111111111", incident["caseId"])
        self.assertEqual({"lon": 101.003, "lat": 13.233}, incident["location"])
        self.assertEqual(
            {
                "level": "HIGH",
                "score": 0.84,
                "source": "external_risk_evaluator",
                "evaluatorVersion": "risk-evaluator-v1",
                "externalAssessmentId": "risk-report-001",
                "createdAt": incident["currentRiskAssessment"]["createdAt"],
            },
            incident["currentRiskAssessment"],
        )
        self.assertEqual(
            f"/api/integrations/v1/reports/{self.report.id}/comments",
            payload["links"]["comments"],
        )
        self.assertEqual(
            f"/api/integrations/v1/reports/{self.report.id}/risk-assessments",
            payload["links"]["riskAssessments"],
        )
        self.assertNotIn("data", incident)
        self.assertNotIn("rendererData", incident)
        self.assertNotIn("originData", incident)
        self.assertNotIn("reportedBy", incident)
        self.assertNotIn("images", incident)
        self.assertNotIn("uploadFiles", incident)

        action_log = IntegrationActionLog.objects.get()
        self.assertEqual("incident.read", action_log.action_type)
        self.assertEqual(IntegrationScope.INCIDENT_READ, action_log.required_scope)
        self.assertEqual("reports.IncidentReport", action_log.target_type)
        self.assertEqual(str(self.report.id), action_log.target_id)
        self.assertEqual(
            IntegrationActionLog.ResultStatus.ACCEPTED,
            action_log.result_status,
        )
        self.assertEqual("[REDACTED]", action_log.request_headers_summary["Authorization"])
        self.assertEqual(str(self.report.id), action_log.result_summary["response"]["incidentId"])

    def test_list_incidents_filters_by_incident_date_authority_hierarchy_and_paginates(self):
        url = (
            "/api/integrations/v1/incidents"
            f"?from=2026-06-01&to=2026-06-30"
            f"&authorityId={self.parent_authority.id}"
            "&includeChildAuthorities=true"
            f"&reportTypeIds={self.report_type.id}"
            "&testFlag=false"
            "&limit=1"
        )

        first_response = self._get(url)
        second_response = self._get(f"{url}&offset=1")

        self.assertEqual(200, first_response.status_code)
        self.assertEqual(200, second_response.status_code)
        first_payload = first_response.json()
        second_payload = second_response.json()
        self.assertEqual(
            {"field": "incident_date", "from": "2026-06-01", "to": "2026-06-30"},
            first_payload["dateFilter"],
        )
        self.assertEqual(
            {
                "limit": 1,
                "offset": 0,
                "count": 1,
                "nextOffset": 1,
            },
            first_payload["pagination"],
        )
        self.assertEqual(str(self.child_report.id), first_payload["incidents"][0]["id"])
        self.assertIn("links", first_payload["incidents"][0])
        self.assertNotIn("data", first_payload["incidents"][0])
        self.assertEqual(
            {
                "limit": 1,
                "offset": 1,
                "count": 1,
                "nextOffset": None,
            },
            second_payload["pagination"],
        )
        self.assertEqual(str(self.report.id), second_payload["incidents"][0]["id"])
        self.assertEqual(
            2,
            IntegrationActionLog.objects.filter(
                result_status=IntegrationActionLog.ResultStatus.ACCEPTED
            ).count(),
        )

    def test_list_limit_above_max_is_capped(self):
        response = self._get("/api/integrations/v1/incidents?limit=1000")

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual(100, payload["pagination"]["limit"])
        self.assertEqual(5, payload["pagination"]["count"])
        self.assertIsNone(payload["pagination"]["nextOffset"])

    def test_large_negative_and_non_integer_offsets_are_rejected(self):
        invalid_queries = [
            "offset=10001",
            "offset=-1",
            "offset=abc",
        ]

        for query in invalid_queries:
            with self.subTest(query=query):
                response = self._get(f"/api/integrations/v1/incidents?{query}")

                self.assertEqual(400, response.status_code)
                self.assertEqual("invalid_query", response.json()["error"]["code"])

        self.assertEqual(len(invalid_queries), IntegrationActionLog.objects.count())
        self.assertEqual(
            {"invalid_query"},
            set(
                IntegrationActionLog.objects.values_list(
                    "result_summary__error__code",
                    flat=True,
                )
            ),
        )

    def test_authority_filter_without_child_authorities_matches_exact_authority_only(self):
        response = self._get(
            "/api/integrations/v1/incidents"
            f"?authorityId={self.parent_authority.id}"
            "&includeChildAuthorities=false"
            "&limit=100"
        )

        self.assertEqual(200, response.status_code)
        incident_ids = [incident["id"] for incident in response.json()["incidents"]]
        self.assertIn(str(self.report.id), incident_ids)
        self.assertIn(str(self.test_report.id), incident_ids)
        self.assertIn(str(self.old_report.id), incident_ids)
        self.assertNotIn(str(self.child_report.id), incident_ids)
        self.assertNotIn(str(self.sibling_report.id), incident_ids)

    def test_village_filter_is_rejected_and_audited_as_unsupported(self):
        responses = [
            self._get("/api/integrations/v1/incidents?villageId=1"),
            self._get("/api/integrations/v1/incidents?villageId="),
        ]

        for response in responses:
            self.assertEqual(400, response.status_code)
            self.assertEqual("invalid_filter", response.json()["error"]["code"])

        self.assertEqual(2, IntegrationActionLog.objects.count())
        self.assertEqual(
            {"invalid_filter"},
            set(
                IntegrationActionLog.objects.values_list(
                    "result_summary__error__code",
                    flat=True,
                )
            ),
        )

    def test_ambiguous_query_filters_are_rejected_as_invalid_query(self):
        invalid_queries = [
            "includeChildAuthorities=true",
            f"authorityId={self.parent_authority.id}&includeChildAuthorities=maybe",
            "testFlag=maybe",
            "reportTypeIds=not-a-uuid",
            "reportTypeIds=",
            "authorityId=",
            "authorityId=abc",
            "authorityId=999999",
        ]

        for query in invalid_queries:
            with self.subTest(query=query):
                response = self._get(f"/api/integrations/v1/incidents?{query}")

                self.assertEqual(400, response.status_code)
                self.assertEqual("invalid_query", response.json()["error"]["code"])

        self.assertEqual(len(invalid_queries), IntegrationActionLog.objects.count())
        self.assertEqual(
            {"invalid_query"},
            set(
                IntegrationActionLog.objects.values_list(
                    "result_summary__error__code",
                    flat=True,
                )
            ),
        )

    def test_missing_functional_scope_is_denied_and_audited(self):
        _application, _integration_client, access_token = self._create_oauth_client(
            "incident-no-scope",
            scope_codes=[],
            token="incident-no-scope-token",
        )

        response = self._get_detail(token=access_token.token)

        self.assertEqual(403, response.status_code)
        self.assertEqual("scope_denied", response.json()["error"]["code"])
        action_log = IntegrationActionLog.objects.get()
        self.assertEqual(
            IntegrationActionLog.ResultStatus.REJECTED,
            action_log.result_status,
        )
        self.assertEqual("scope_denied", action_log.result_summary["error"]["code"])

    def test_user_bound_oauth_token_is_denied_even_for_valid_service_application(self):
        _application, _integration_client, access_token = self._create_oauth_client(
            "incident-human-token",
            scope_codes=[IntegrationScope.INCIDENT_READ],
            token="incident-human-token",
            token_user=self.reporter,
        )

        response = self._get_detail(token=access_token.token)

        self.assertEqual(403, response.status_code)
        self.assertEqual("service_identity_denied", response.json()["error"]["code"])
        action_log = IntegrationActionLog.objects.get()
        self.assertEqual(
            "service_identity_denied",
            action_log.result_summary["error"]["code"],
        )

    def test_missing_bearer_token_is_not_accepted_as_browser_or_cookie_auth(self):
        response = self.client.get(self._detail_url())

        self.assertEqual(401, response.status_code)
        self.assertEqual("oauth_required", response.json()["error"]["code"])
        self.assertEqual(0, IntegrationActionLog.objects.count())

    def test_public_schema_is_denied_before_integration_authorization(self):
        public_client = Client()
        try:
            response = public_client.get(
                self._detail_url(),
                HTTP_AUTHORIZATION=f"Bearer {self.access_token.token}",
            )
        finally:
            connection.set_tenant(self.tenant)

        self.assertEqual(403, response.status_code)
        self.assertEqual("tenant_denied", response.json()["error"]["code"])
        self.assertEqual(0, IntegrationActionLog.objects.count())

    def test_missing_incident_is_rejected_and_audited(self):
        missing_report_id = "22222222-2222-2222-2222-222222222222"
        response = self._get(f"/api/integrations/v1/incidents/{missing_report_id}")

        self.assertEqual(404, response.status_code)
        self.assertEqual("incident_not_found", response.json()["error"]["code"])
        action_log = IntegrationActionLog.objects.get()
        self.assertEqual(missing_report_id, action_log.target_id)
        self.assertEqual(
            "incident_not_found",
            action_log.result_summary["error"]["code"],
        )

    def test_invalid_date_filter_is_rejected_and_audited(self):
        response = self._get("/api/integrations/v1/incidents?from=not-a-date")

        self.assertEqual(400, response.status_code)
        self.assertEqual("invalid_query", response.json()["error"]["code"])
        action_log = IntegrationActionLog.objects.get()
        self.assertEqual("invalid_query", action_log.result_summary["error"]["code"])
        self.assertEqual("not-a-date", action_log.result_summary["querySummary"]["from"])

    def _create_report(
        self,
        symptom,
        authority,
        *,
        incident_date,
        report_type=None,
        gps_location=None,
        case_id=None,
        test_flag=False,
    ):
        report = IncidentReport.objects.create(
            data={
                "symptom": symptom,
                "token": "private-report-input",
                "privateFormValue": "not-for-integrations",
            },
            reported_by=self.reporter,
            incident_date=incident_date,
            report_type=report_type or self.report_type,
            gps_location=gps_location,
            case_id=case_id,
            test_flag=test_flag,
        )
        report.relevant_authorities.add(authority)
        return report

    def _create_oauth_client(
        self,
        code,
        scope_codes,
        token,
        token_user=None,
        integration_type=IntegrationClient.IntegrationType.AI_ASSISTANT,
    ):
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
            integration_type=integration_type,
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

    def _get_detail(self, token=None):
        return self._get(self._detail_url(), token=token)

    def _get(self, url, token=None):
        return self.client.get(
            url,
            HTTP_AUTHORIZATION=f"Bearer {token or self.access_token.token}",
        )

    def _detail_url(self):
        return f"/api/integrations/v1/incidents/{self.report.id}"
