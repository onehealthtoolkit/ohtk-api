import uuid
from datetime import date
from decimal import Decimal

from django.db import connection
from django.test import RequestFactory
from django_tenants.test.cases import TenantTestCase
from oauth2_provider.models import get_application_model

from accounts.models import Authority, AuthorityUser
from integrations.constants import IntegrationScope
from integrations.models import IntegrationClient, IntegrationClusterResult
from podd_api.schema import schema
from reports.models import Category, IncidentReport, ReportType


class ClusterDashboardGraphqlTests(TenantTestCase):
    @classmethod
    def setup_tenant(cls, tenant):
        tenant.name = "Tenant Alpha"

    def setUp(self):
        super().setUp()
        connection.set_tenant(self.tenant)
        self.request_factory = RequestFactory()
        self.authority = Authority.objects.create(code="BKK", name="Bangkok")
        self.other_authority = Authority.objects.create(code="CM", name="Chiangmai")
        self.user = AuthorityUser.objects.create(
            username="operator",
            authority=self.authority,
            role=AuthorityUser.Role.OFFICER,
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
            renderer_data_template="Animal cluster report",
        )
        self.report_type.authorities.add(self.authority)
        self.report = self._create_report(self.authority)
        self.integration_client = self._create_integration_client()

    def test_cluster_results_are_scoped_filterable_and_include_linked_reports(self):
        matching_cluster = self._create_cluster_result(
            external_cluster_id="cluster-dashboard-match",
            authority_ids=[self.authority.id],
            incident_ids=[str(self.report.id)],
            risk_level="HIGH",
            score=Decimal("0.9100"),
        )
        self._create_cluster_result(
            external_cluster_id="cluster-dashboard-other",
            authority_ids=[self.other_authority.id],
            incident_ids=[str(uuid.uuid4())],
            risk_level="LOW",
            score=Decimal("0.2000"),
        )

        result = self.execute(
            """
            query dashboardClusters($levels: String) {
              clusterResults(limit: 20, offset: 0, riskLevels: $levels) {
                totalCount
                results {
                  id
                  externalClusterId
                  algorithmVersion
                  windowStart
                  windowEnd
                  riskLevel
                  score
                  radiusMeters
                  reportCount
                  explanation
                  metadata
                  integrationClient {
                    code
                    name
                  }
                  linkedReports {
                    id
                    rendererData
                    reportType {
                      name
                    }
                  }
                }
              }
            }
            """,
            {"levels": "HIGH"},
        )

        self.assertIsNone(result.errors, result.errors)
        payload = result.data["clusterResults"]
        self.assertEqual(1, payload["totalCount"])
        cluster = payload["results"][0]
        self.assertEqual(str(matching_cluster.cluster_id), cluster["id"])
        self.assertEqual("cluster-dashboard-match", cluster["externalClusterId"])
        self.assertEqual("detector-v1", cluster["algorithmVersion"])
        self.assertEqual("2026-06-01", cluster["windowStart"])
        self.assertEqual("2026-06-07", cluster["windowEnd"])
        self.assertEqual("HIGH", cluster["riskLevel"])
        self.assertEqual(0.91, cluster["score"])
        self.assertEqual(250.5, cluster["radiusMeters"])
        self.assertEqual(1, cluster["reportCount"])
        self.assertEqual({"status": "NEW"}, cluster["metadata"])
        self.assertEqual("cluster-client", cluster["integrationClient"]["code"])
        self.assertEqual(str(self.report.id), cluster["linkedReports"][0]["id"])
        self.assertEqual(
            "Animal Sick/Death",
            cluster["linkedReports"][0]["reportType"]["name"],
        )

    def test_cluster_result_detail_uses_public_cluster_id(self):
        cluster = self._create_cluster_result(
            external_cluster_id="cluster-dashboard-detail",
            authority_ids=[self.authority.id],
            incident_ids=[str(self.report.id)],
        )

        result = self.execute(
            """
            query clusterDetail($id: UUID!) {
              clusterResult(id: $id) {
                id
                externalClusterId
                linkedReports {
                  id
                }
              }
            }
            """,
            {"id": str(cluster.cluster_id)},
        )

        self.assertIsNone(result.errors, result.errors)
        payload = result.data["clusterResult"]
        self.assertEqual(str(cluster.cluster_id), payload["id"])
        self.assertEqual("cluster-dashboard-detail", payload["externalClusterId"])
        self.assertEqual([{"id": str(self.report.id)}], payload["linkedReports"])

    def execute(self, query, variables=None):
        request = self.request_factory.post("/graphql/")
        request.user = self.user
        return schema.execute(
            query,
            variable_values=variables or {},
            context_value=request,
        )

    def _create_report(self, authority):
        report = IncidentReport.objects.create(
            reported_by=self.reporter,
            report_type=self.report_type,
            data={"symptom": "sudden death"},
            incident_date=date(2026, 6, 2),
            relevant_authority_resolved=True,
        )
        report.relevant_authorities.add(authority)
        return report

    def _create_integration_client(self):
        application_model = get_application_model()
        application = application_model.objects.create(
            name="cluster-client",
            user=None,
            client_type=application_model.CLIENT_CONFIDENTIAL,
            authorization_grant_type=application_model.GRANT_CLIENT_CREDENTIALS,
        )
        return IntegrationClient.objects.create(
            name="cluster-client",
            code="cluster-client",
            integration_type=IntegrationClient.IntegrationType.CLUSTER_DETECTOR,
            oauth_application=application,
            scope_codes=[IntegrationScope.CLUSTER_WRITE_RESULT],
        )

    def _create_cluster_result(
        self,
        external_cluster_id,
        authority_ids,
        incident_ids,
        risk_level="MEDIUM",
        score=Decimal("0.5000"),
    ):
        return IntegrationClusterResult.objects.create(
            integration_client=self.integration_client,
            external_cluster_id=external_cluster_id,
            algorithm_version="detector-v1",
            window_start=date(2026, 6, 1),
            window_end=date(2026, 6, 7),
            incident_ids=incident_ids,
            authority_ids=authority_ids,
            village_ids=[],
            geometry={"type": "Point", "coordinates": [100.5, 13.7]},
            radius_meters=Decimal("250.500"),
            score=score,
            risk_level=risk_level,
            explanation="Detector found a possible report cluster.",
            metadata={"status": "NEW"},
        )
