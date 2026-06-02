import json
import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.db import IntegrityError, connection
from django.test import Client
from django.urls import resolve
from django.utils import timezone
from django_tenants.test.cases import TenantTestCase
from django_tenants.test.client import TenantClient
from oauth2_provider.models import get_access_token_model, get_application_model

from accounts.models import Authority, AuthorityUser, Village
from integrations.constants import IntegrationScope
from integrations.models import (
    IntegrationActionLog,
    IntegrationClient,
    IntegrationClusterResult,
    IntegrationIdempotencyRecord,
    RiskAssessment,
)
from reports.models import Category, IncidentReport, ReportType


class ClusterResultApiTests(TenantTestCase):
    @classmethod
    def setup_tenant(cls, tenant):
        tenant.name = "Tenant Alpha"

    def setUp(self):
        connection.set_tenant(self.tenant)
        self.client = TenantClient(self.tenant)
        self.authority = Authority.objects.create(code="BKK", name="Bangkok")
        self.other_authority = Authority.objects.create(code="CM", name="Chiangmai")
        self.village = Village.objects.create(
            authority=self.authority,
            code="V001",
            name="Village One",
        )
        self.other_village = Village.objects.create(
            authority=self.other_authority,
            code="V002",
            name="Village Two",
        )
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
                "cluster-client",
                scope_codes=[IntegrationScope.CLUSTER_WRITE_RESULT],
                token="cluster-token",
            )
        )

    def test_endpoints_are_exposed_at_versioned_cluster_paths(self):
        cluster_id = uuid.uuid4()

        list_match = resolve("/api/integrations/v1/clusters")
        detail_match = resolve(f"/api/integrations/v1/clusters/{cluster_id}")

        self.assertEqual("integration-clusters", list_match.url_name)
        self.assertEqual("integration-cluster-detail", detail_match.url_name)

    def test_create_cluster_result_stores_result_and_audit(self):
        payload = self._cluster_payload(
            external_cluster_id="cluster-ext-001",
            metadata={
                "model": "cluster-detector-v1",
                "clientSecret": "plain-secret",
                "headers": [{"name": "X-Api-Key", "value": "plain-key"}],
            },
        )

        response = self._post_cluster(payload, idempotency_key="idem-cluster-001")

        self.assertEqual(202, response.status_code)
        response_payload = response.json()
        self.assertEqual("2026-06-02", response_payload["schemaVersion"])
        self.assertEqual("accepted", response_payload["status"])
        cluster_payload = response_payload["cluster"]
        self.assertEqual("cluster-ext-001", cluster_payload["externalClusterId"])
        self.assertEqual("detector-v1", cluster_payload["algorithmVersion"])
        self.assertEqual(
            {"from": "2026-06-01", "to": "2026-06-07"},
            cluster_payload["window"],
        )
        self.assertEqual([str(self.report.id)], cluster_payload["incidentIds"])
        self.assertEqual([self.authority.id], cluster_payload["authorityIds"])
        self.assertEqual([self.village.id], cluster_payload["villageIds"])
        self.assertEqual({"type": "Point", "coordinates": [101.0, 13.2]}, cluster_payload["geometry"])
        self.assertEqual(250.5, cluster_payload["radiusMeters"])
        self.assertEqual(0.91, cluster_payload["score"])
        self.assertEqual("HIGH", cluster_payload["riskLevel"])
        self.assertEqual("Detector found a mortality cluster.", cluster_payload["explanation"])
        self.assertEqual(
            {
                "code": "cluster-client",
                "name": "cluster-client",
            },
            cluster_payload["integrationClient"],
        )

        stored_cluster = IntegrationClusterResult.objects.get()
        self.assertEqual(cluster_payload["id"], str(stored_cluster.cluster_id))
        self.assertEqual(self.integration_client, stored_cluster.integration_client)
        self.assertEqual("cluster-ext-001", stored_cluster.external_cluster_id)
        self.assertEqual(Decimal("250.500"), stored_cluster.radius_meters)
        self.assertEqual(Decimal("0.9100"), stored_cluster.score)
        self.assertEqual(
            {
                "model": "cluster-detector-v1",
                "clientSecret": "[REDACTED]",
                "headers": [{"name": "X-Api-Key", "value": "[REDACTED]"}],
            },
            stored_cluster.metadata,
        )
        self.assertEqual(
            0,
            RiskAssessment.objects.filter(
                target_type=RiskAssessment.TargetType.CLUSTER
            ).count(),
        )

        action_log = IntegrationActionLog.objects.get(
            result_status=IntegrationActionLog.ResultStatus.ACCEPTED
        )
        self.assertEqual("cluster.write_result", action_log.action_type)
        self.assertEqual(
            IntegrationScope.CLUSTER_WRITE_RESULT,
            action_log.required_scope,
        )
        self.assertEqual(
            "integrations.IntegrationClusterResult",
            action_log.target_type,
        )
        self.assertEqual(str(stored_cluster.cluster_id), action_log.target_id)
        self.assertEqual("idem-cluster-001", action_log.idempotency_key)
        self.assertEqual("cluster-ext-001", action_log.external_action_id)
        self.assertEqual("[REDACTED]", action_log.request_headers_summary["Authorization"])
        self.assertEqual(
            "[REDACTED]",
            action_log.result_summary["payloadSummary"]["metadata"]["clientSecret"],
        )
        self.assertEqual(action_log, stored_cluster.action_log)

        idempotency = IntegrationIdempotencyRecord.objects.get()
        self.assertEqual(action_log, idempotency.action_log)
        self.assertEqual(202, idempotency.response_status_code)
        self.assertEqual(response_payload, idempotency.response_summary)

    def test_external_cluster_id_can_supply_idempotency_key(self):
        response = self._post_cluster(
            self._cluster_payload(external_cluster_id="cluster-body-key")
        )

        self.assertEqual(202, response.status_code)
        idempotency = IntegrationIdempotencyRecord.objects.get()
        self.assertEqual("cluster-body-key", idempotency.key)

    def test_same_idempotency_key_and_payload_replays_same_cluster(self):
        payload = self._cluster_payload(external_cluster_id="cluster-replay")

        first = self._post_cluster(payload, idempotency_key="idem-cluster-replay")
        second = self._post_cluster(payload, idempotency_key="idem-cluster-replay")

        self.assertEqual(202, first.status_code)
        self.assertEqual(202, second.status_code)
        self.assertEqual("accepted", first.json()["status"])
        self.assertEqual("replayed", second.json()["status"])
        self.assertEqual(first.json()["cluster"], second.json()["cluster"])
        self.assertEqual(1, IntegrationClusterResult.objects.count())
        self.assertEqual(1, IntegrationIdempotencyRecord.objects.count())
        self.assertEqual(
            1,
            IntegrationActionLog.objects.filter(
                result_status=IntegrationActionLog.ResultStatus.REPLAYED
            ).count(),
        )

    def test_same_idempotency_key_with_different_payload_conflicts(self):
        first = self._post_cluster(
            self._cluster_payload(external_cluster_id="cluster-conflict-a"),
            idempotency_key="idem-cluster-conflict",
        )
        second = self._post_cluster(
            self._cluster_payload(external_cluster_id="cluster-conflict-b"),
            idempotency_key="idem-cluster-conflict",
        )

        self.assertEqual(202, first.status_code)
        self.assertEqual(409, second.status_code)
        self.assertEqual(
            "idempotency_conflict",
            second.json()["error"]["code"],
        )
        self.assertEqual(1, IntegrationClusterResult.objects.count())

    def test_same_external_cluster_id_with_different_idempotency_key_conflicts(self):
        payload = self._cluster_payload(external_cluster_id="cluster-ext-conflict")

        first = self._post_cluster(payload, idempotency_key="idem-cluster-a")
        second = self._post_cluster(payload, idempotency_key="idem-cluster-b")

        self.assertEqual(202, first.status_code)
        self.assertEqual(409, second.status_code)
        self.assertEqual("cluster_result_conflict", second.json()["error"]["code"])
        self.assertEqual(1, IntegrationClusterResult.objects.count())
        self.assertEqual(1, IntegrationIdempotencyRecord.objects.count())

    def test_unique_constraint_integrity_error_returns_cluster_result_conflict(self):
        payload = self._cluster_payload(external_cluster_id="cluster-race-conflict")
        duplicate_error = IntegrityError(
            'duplicate key value violates unique constraint '
            '"unique_active_integration_cluster_external"'
        )

        with patch(
            "integrations.views.IntegrationClusterResult.objects.create",
            side_effect=duplicate_error,
        ):
            response = self._post_cluster(
                payload,
                idempotency_key="idem-cluster-race-conflict",
            )

        self.assertEqual(409, response.status_code)
        self.assertEqual("cluster_result_conflict", response.json()["error"]["code"])
        self.assertEqual(0, IntegrationClusterResult.objects.count())
        self.assertEqual(0, IntegrationIdempotencyRecord.objects.count())
        action_log = IntegrationActionLog.objects.get()
        self.assertEqual(
            "cluster_result_conflict",
            action_log.result_summary["error"]["code"],
        )

    def test_list_clusters_filters_by_window_overlap_targets_and_risk(self):
        matching_cluster = self._create_cluster_result(
            external_cluster_id="cluster-list-match",
            window_start="2026-06-01",
            window_end="2026-06-07",
            authority_ids=[self.authority.id],
            village_ids=[self.village.id],
            risk_level="HIGH",
        )
        self._create_cluster_result(
            external_cluster_id="cluster-list-outside",
            window_start="2026-05-01",
            window_end="2026-05-03",
            authority_ids=[self.other_authority.id],
            village_ids=[self.other_village.id],
            risk_level="LOW",
        )
        url = (
            "/api/integrations/v1/clusters"
            "?from=2026-06-05&to=2026-06-08"
            f"&authorityId={self.authority.id}"
            f"&villageId={self.village.id}"
            "&riskLevel=HIGH"
            "&limit=1"
        )

        response = self._get(url)

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual(
            {"field": "window_overlap", "from": "2026-06-05", "to": "2026-06-08"},
            payload["dateFilter"],
        )
        self.assertEqual(
            {"limit": 1, "offset": 0, "count": 1, "nextOffset": None},
            payload["pagination"],
        )
        self.assertEqual(
            str(matching_cluster.cluster_id),
            payload["clusters"][0]["id"],
        )
        self.assertNotIn("incidentDetails", payload["clusters"][0])
        self.assertNotIn("census", payload["clusters"][0])

        action_log = IntegrationActionLog.objects.get()
        self.assertEqual("cluster.read", action_log.action_type)
        self.assertEqual(IntegrationScope.CLUSTER_WRITE_RESULT, action_log.required_scope)
        self.assertEqual("2026-06-05", action_log.result_summary["querySummary"]["from"])

    def test_cluster_reads_are_scoped_to_authenticated_integration_client(self):
        _other_application, other_client, other_token = self._create_oauth_client(
            "cluster-client-b",
            scope_codes=[IntegrationScope.CLUSTER_WRITE_RESULT],
            token="cluster-token-b",
        )
        own_cluster = self._create_cluster_result(
            external_cluster_id="cluster-own-client"
        )
        other_cluster = self._create_cluster_result(
            external_cluster_id="cluster-other-client",
            integration_client=other_client,
        )

        owner_list = self._get("/api/integrations/v1/clusters")
        other_detail_for_owner = self._get(
            f"/api/integrations/v1/clusters/{other_cluster.cluster_id}"
        )
        other_detail = self._get(
            f"/api/integrations/v1/clusters/{other_cluster.cluster_id}",
            token=other_token.token,
        )
        other_list = self._get(
            "/api/integrations/v1/clusters",
            token=other_token.token,
        )

        self.assertEqual(200, owner_list.status_code)
        owner_cluster_ids = {
            cluster["id"] for cluster in owner_list.json()["clusters"]
        }
        self.assertEqual({str(own_cluster.cluster_id)}, owner_cluster_ids)
        self.assertNotIn(str(other_cluster.cluster_id), owner_cluster_ids)

        self.assertEqual(404, other_detail_for_owner.status_code)
        self.assertEqual(
            "cluster_not_found",
            other_detail_for_owner.json()["error"]["code"],
        )

        self.assertEqual(200, other_detail.status_code)
        self.assertEqual(
            str(other_cluster.cluster_id),
            other_detail.json()["cluster"]["id"],
        )

        self.assertEqual(200, other_list.status_code)
        other_cluster_ids = {
            cluster["id"] for cluster in other_list.json()["clusters"]
        }
        self.assertEqual({str(other_cluster.cluster_id)}, other_cluster_ids)

    def test_read_cluster_detail_returns_thin_payload_and_audits(self):
        cluster = self._create_cluster_result(external_cluster_id="cluster-detail")

        response = self._get(f"/api/integrations/v1/clusters/{cluster.cluster_id}")

        self.assertEqual(200, response.status_code)
        payload = response.json()
        cluster_payload = payload["cluster"]
        self.assertEqual(str(cluster.cluster_id), cluster_payload["id"])
        self.assertEqual("cluster-detail", cluster_payload["externalClusterId"])
        self.assertEqual("detector-v1", cluster_payload["algorithmVersion"])
        self.assertNotIn("incidentDetails", cluster_payload)
        self.assertNotIn("census", cluster_payload)

        action_log = IntegrationActionLog.objects.get()
        self.assertEqual("cluster.read", action_log.action_type)
        self.assertEqual(
            "integrations.IntegrationClusterResult",
            action_log.target_type,
        )
        self.assertEqual(str(cluster.cluster_id), action_log.target_id)

    def test_missing_cluster_detail_is_rejected_and_audited(self):
        missing_cluster_id = uuid.uuid4()

        response = self._get(f"/api/integrations/v1/clusters/{missing_cluster_id}")

        self.assertEqual(404, response.status_code)
        self.assertEqual("cluster_not_found", response.json()["error"]["code"])
        action_log = IntegrationActionLog.objects.get()
        self.assertEqual(str(missing_cluster_id), action_log.target_id)
        self.assertEqual(
            "cluster_not_found",
            action_log.result_summary["error"]["code"],
        )

    def test_invalid_cluster_payload_shapes_are_rejected_and_audited(self):
        invalid_payloads = [
            {},
            self._cluster_payload(external_cluster_id=""),
            self._cluster_payload(algorithm_version=""),
            self._cluster_payload(window={"from": "2026-06-08", "to": "2026-06-01"}),
            self._cluster_payload(incident_ids=["not-a-uuid"]),
            self._cluster_payload(incident_ids=[str(uuid.uuid4())]),
            self._cluster_payload(authority_ids=["1"]),
            self._cluster_payload(authority_ids=[999999]),
            self._cluster_payload(village_ids=[999999]),
            self._cluster_payload(geometry=[]),
            self._cluster_payload(radius_meters=-1),
            self._cluster_payload(score="0.5"),
            self._cluster_payload(score=1.5),
            self._cluster_payload(risk_level="SEVERE"),
            self._cluster_payload(risk_level=""),
            self._cluster_payload(metadata=[]),
            self._cluster_payload(extra={"target": "unsupported"}),
        ]

        for index, payload in enumerate(invalid_payloads, start=1):
            with self.subTest(payload=payload):
                response = self._post_cluster(
                    payload,
                    idempotency_key=f"idem-invalid-cluster-{index}",
                )

                self.assertEqual(400, response.status_code)
                self.assertEqual("invalid_payload", response.json()["error"]["code"])

        self.assertEqual(0, IntegrationClusterResult.objects.count())
        self.assertEqual(len(invalid_payloads), IntegrationActionLog.objects.count())
        self.assertEqual(0, IntegrationIdempotencyRecord.objects.count())

    def test_ambiguous_cluster_queries_are_rejected_as_invalid_query(self):
        invalid_queries = [
            "unknown=1",
            "from=",
            "from=not-a-date",
            "from=2026-06-10&to=2026-06-01",
            "authorityId=",
            "authorityId=abc",
            "authorityId=999999",
            "villageId=999999",
            "riskLevel=SEVERE",
            "limit=0",
            "offset=10001",
            "externalClusterId=a&externalClusterId=b",
        ]

        for query in invalid_queries:
            with self.subTest(query=query):
                response = self._get(f"/api/integrations/v1/clusters?{query}")

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
            "cluster-no-scope",
            scope_codes=[],
            token="cluster-no-scope-token",
        )

        response = self._post_cluster(
            self._cluster_payload(external_cluster_id="cluster-no-scope"),
            idempotency_key="idem-cluster-no-scope",
            token=access_token.token,
        )

        self.assertEqual(403, response.status_code)
        self.assertEqual("scope_denied", response.json()["error"]["code"])
        self.assertEqual(0, IntegrationClusterResult.objects.count())
        action_log = IntegrationActionLog.objects.get()
        self.assertEqual("scope_denied", action_log.result_summary["error"]["code"])

    def test_user_bound_oauth_token_is_denied_even_for_valid_service_application(self):
        _application, _integration_client, access_token = self._create_oauth_client(
            "cluster-human-token",
            scope_codes=[IntegrationScope.CLUSTER_WRITE_RESULT],
            token="cluster-human-token",
            token_user=self.reporter,
        )

        response = self._post_cluster(
            self._cluster_payload(external_cluster_id="cluster-human-token"),
            idempotency_key="idem-cluster-human-token",
            token=access_token.token,
        )

        self.assertEqual(403, response.status_code)
        self.assertEqual("service_identity_denied", response.json()["error"]["code"])
        self.assertEqual(0, IntegrationClusterResult.objects.count())
        action_log = IntegrationActionLog.objects.get()
        self.assertEqual(
            "service_identity_denied",
            action_log.result_summary["error"]["code"],
        )

    def test_missing_bearer_token_is_not_accepted_as_browser_or_cookie_auth(self):
        response = self.client.post(
            "/api/integrations/v1/clusters",
            data=json.dumps(
                self._cluster_payload(external_cluster_id="cluster-no-token")
            ),
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY="idem-cluster-no-token",
        )

        self.assertEqual(401, response.status_code)
        self.assertEqual("oauth_required", response.json()["error"]["code"])
        self.assertEqual(0, IntegrationClusterResult.objects.count())
        self.assertEqual(0, IntegrationActionLog.objects.count())

    def test_public_schema_is_denied_before_integration_authorization(self):
        public_client = Client()
        try:
            response = public_client.post(
                "/api/integrations/v1/clusters",
                data=json.dumps(
                    self._cluster_payload(external_cluster_id="cluster-public")
                ),
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {self.access_token.token}",
                HTTP_IDEMPOTENCY_KEY="idem-cluster-public",
            )
        finally:
            connection.set_tenant(self.tenant)

        self.assertEqual(403, response.status_code)
        self.assertEqual("tenant_denied", response.json()["error"]["code"])
        self.assertEqual(0, IntegrationClusterResult.objects.count())
        self.assertEqual(0, IntegrationActionLog.objects.count())

    def _cluster_payload(
        self,
        *,
        external_cluster_id="cluster-ext-default",
        algorithm_version="detector-v1",
        window=None,
        incident_ids=None,
        authority_ids=None,
        village_ids=None,
        geometry=None,
        radius_meters=250.5,
        score=0.91,
        risk_level="HIGH",
        explanation="Detector found a mortality cluster.",
        metadata=None,
        extra=None,
    ):
        payload = {
            "externalClusterId": external_cluster_id,
            "algorithmVersion": algorithm_version,
            "window": window or {"from": "2026-06-01", "to": "2026-06-07"},
            "incidentIds": incident_ids
            if incident_ids is not None
            else [str(self.report.id)],
            "authorityIds": authority_ids
            if authority_ids is not None
            else [self.authority.id],
            "villageIds": village_ids if village_ids is not None else [self.village.id],
            "geometry": geometry
            if geometry is not None
            else {"type": "Point", "coordinates": [101.0, 13.2]},
            "radiusMeters": radius_meters,
            "score": score,
            "riskLevel": risk_level,
            "explanation": explanation,
            "metadata": metadata if metadata is not None else {"model": "detector-v1"},
        }
        if extra:
            payload.update(extra)
        return payload

    def _create_cluster_result(
        self,
        *,
        external_cluster_id,
        window_start="2026-06-01",
        window_end="2026-06-07",
        authority_ids=None,
        village_ids=None,
        risk_level="HIGH",
        integration_client=None,
    ):
        return IntegrationClusterResult.objects.create(
            integration_client=integration_client or self.integration_client,
            external_cluster_id=external_cluster_id,
            algorithm_version="detector-v1",
            window_start=timezone.datetime.fromisoformat(window_start).date(),
            window_end=timezone.datetime.fromisoformat(window_end).date(),
            incident_ids=[str(self.report.id)],
            authority_ids=authority_ids if authority_ids is not None else [self.authority.id],
            village_ids=village_ids if village_ids is not None else [self.village.id],
            geometry={"type": "Point", "coordinates": [101.0, 13.2]},
            radius_meters=Decimal("250.500"),
            score=Decimal("0.9100"),
            risk_level=risk_level,
            explanation="Stored fixture cluster.",
            metadata={"model": "detector-v1"},
        )

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
            integration_type=IntegrationClient.IntegrationType.CLUSTER_DETECTOR,
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

    def _post_cluster(self, payload, idempotency_key=None, token=None):
        headers = {
            "HTTP_AUTHORIZATION": f"Bearer {token or self.access_token.token}",
        }
        if idempotency_key:
            headers["HTTP_IDEMPOTENCY_KEY"] = idempotency_key

        return self.client.post(
            "/api/integrations/v1/clusters",
            data=json.dumps(payload),
            content_type="application/json",
            **headers,
        )

    def _get(self, url, token=None):
        return self.client.get(
            url,
            HTTP_AUTHORIZATION=f"Bearer {token or self.access_token.token}",
        )
