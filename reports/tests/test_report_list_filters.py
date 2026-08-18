from datetime import date

from django.test import RequestFactory
from django.utils.timezone import now
from django_tenants.test.cases import TenantTestCase
from django.db import connection

from accounts.models import Authority, AuthorityUser
from podd_api.schema import schema
from reports.models import Category, IncidentReport, ReportType


class ReportListFilterTests(TenantTestCase):
    def setup_tenant(self, tenant):
        tenant.name = "Tenant Alpha"

    def setUp(self):
        super().setUp()
        connection.set_tenant(self.tenant)
        self.request_factory = RequestFactory()
        self.authority = Authority.objects.create(code="BKK", name="Bangkok")
        self.user = AuthorityUser.objects.create(
            username="operator",
            authority=self.authority,
            is_superuser=True,
        )
        self.category = Category.objects.create(name="animal")
        self.report_type = ReportType.objects.create(
            name="Animal Sick/Death",
            category=self.category,
            definition={},
            published=True,
        )
        self.report_type.authorities.add(self.authority)

    def _create_report(self, **kwargs):
        defaults = {
            "reported_by": self.user,
            "report_type": self.report_type,
            "data": {},
            "incident_date": date(2026, 8, 1),
            "relevant_authority_resolved": True,
            "renderer_data": "Cattle 3 heads",
            "ai_suspected": "",
        }
        defaults.update(kwargs)
        report = IncidentReport.objects.create(**defaults)
        report.relevant_authorities.add(self.authority)
        return report

    def execute(self, query, variables=None):
        request = self.request_factory.post("/graphql/")
        request.user = self.user
        return schema.execute(
            query,
            variable_values=variables or {},
            context_value=request,
        )

    def test_q_matches_renderer_data_or_ai_suspected(self):
        cattle = self._create_report(renderer_data="Cattle 3 heads")
        fmd = self._create_report(
            renderer_data="Pig 1 head", ai_suspected="possible FMD"
        )
        other = self._create_report(renderer_data="Duck 2 heads")

        result = self.execute(
            """
            query($q: String) {
              incidentReports(q: $q, limit: 20, offset: 0) {
                results { id }
              }
            }
            """,
            {"q": "Cattle"},
        )
        self.assertIsNone(result.errors, result.errors)
        ids = {item["id"] for item in result.data["incidentReports"]["results"]}
        self.assertEqual(ids, {str(cattle.id)})

        result = self.execute(
            """
            query($q: String) {
              incidentReports(q: $q, limit: 20, offset: 0) {
                results { id }
              }
            }
            """,
            {"q": "FMD"},
        )
        self.assertIsNone(result.errors, result.errors)
        ids = {item["id"] for item in result.data["incidentReports"]["results"]}
        self.assertEqual(ids, {str(fmd.id)})
        self.assertNotIn(str(other.id), ids)

    def test_blank_q_does_not_filter(self):
        first = self._create_report()
        second = self._create_report(renderer_data="Pig")
        result = self.execute(
            """
            query {
              incidentReports(q: "   ", limit: 20, offset: 0) {
                results { id }
              }
            }
            """
        )
        self.assertIsNone(result.errors, result.errors)
        ids = {item["id"] for item in result.data["incidentReports"]["results"]}
        self.assertEqual(ids, {str(first.id), str(second.id)})

    def test_only_case_returns_promoted_reports(self):
        promoted = self._create_report()
        promoted.case_id = "11111111-1111-1111-1111-111111111111"
        promoted.save(update_fields=["case_id"])
        self._create_report()

        result = self.execute(
            """
            query {
              incidentReports(onlyCase: true, limit: 20, offset: 0) {
                results { id }
              }
            }
            """
        )
        self.assertIsNone(result.errors, result.errors)
        ids = {item["id"] for item in result.data["incidentReports"]["results"]}
        self.assertEqual(ids, {str(promoted.id)})

    def test_incident_date_range(self):
        early = self._create_report(incident_date=date(2026, 7, 1))
        mid = self._create_report(incident_date=date(2026, 8, 10))
        late = self._create_report(incident_date=date(2026, 9, 1))

        result = self.execute(
            """
            query {
              incidentReports(
                incidentDate_Gte: "2026-08-01"
                incidentDate_Lte: "2026-08-31"
                limit: 20
                offset: 0
              ) {
                results { id }
              }
            }
            """
        )
        self.assertIsNone(result.errors, result.errors)
        ids = {item["id"] for item in result.data["incidentReports"]["results"]}
        self.assertEqual(ids, {str(mid.id)})
        self.assertNotIn(str(early.id), ids)
        self.assertNotIn(str(late.id), ids)
