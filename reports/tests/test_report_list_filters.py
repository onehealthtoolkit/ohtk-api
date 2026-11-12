from datetime import date

from django.test import RequestFactory
from django.utils.timezone import now
from django_tenants.test.cases import TenantTestCase
from django.db import connection

from accounts.models import Authority, AuthorityUser, Village
from podd_api.schema import schema
from reports.models import Category, IncidentReport, ReportType


class ReportListFilterTests(TenantTestCase):
    @classmethod
    def setup_tenant(cls, tenant):
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
        renderer_data = kwargs.pop("renderer_data", "Cattle 3 heads")
        ai_suspected = kwargs.pop("ai_suspected", "")
        defaults = {
            "reported_by": self.user,
            "report_type": self.report_type,
            "data": {},
            "incident_date": date(2026, 8, 1),
            "relevant_authority_resolved": True,
        }
        defaults.update(kwargs)
        report = IncidentReport.objects.create(**defaults)
        report.relevant_authorities.add(self.authority)
        # IncidentReport.save() overwrites renderer_data from the type template.
        IncidentReport.objects.filter(pk=report.pk).update(
            renderer_data=renderer_data,
            ai_suspected=ai_suspected,
        )
        report.refresh_from_db()
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

    def test_village_id_in_filters_by_report_village(self):
        village_a = Village.objects.create(
            authority=self.authority, code="V-A", name="Village A", active=True
        )
        village_b = Village.objects.create(
            authority=self.authority, code="V-B", name="Village B", active=True
        )
        in_a = self._create_report(village=village_a)
        self._create_report(village=village_b)
        self._create_report()

        result = self.execute(
            """
            query($villageIds: [ID]) {
              incidentReports(village_Id_In: $villageIds, limit: 20, offset: 0) {
                results { id }
              }
            }
            """,
            {"villageIds": [str(village_a.id)]},
        )
        self.assertIsNone(result.errors, result.errors)
        ids = {item["id"] for item in result.data["incidentReports"]["results"]}
        self.assertEqual(ids, {str(in_a.id)})

    def test_empty_village_id_in_does_not_filter(self):
        village = Village.objects.create(
            authority=self.authority, code="V-E", name="Village Empty", active=True
        )
        with_village = self._create_report(village=village)
        without_village = self._create_report()

        result = self.execute(
            """
            query {
              incidentReports(village_Id_In: [], limit: 20, offset: 0) {
                results { id }
              }
            }
            """
        )
        self.assertIsNone(result.errors, result.errors)
        ids = {item["id"] for item in result.data["incidentReports"]["results"]}
        self.assertEqual(ids, {str(with_village.id), str(without_village.id)})

    def _authority_hierarchy_reports(self):
        child = Authority.objects.create(code="child", name="District")
        child.inherits.add(self.authority)
        grandchild = Authority.objects.create(code="grandchild", name="Commune")
        grandchild.inherits.add(child)
        outside = Authority.objects.create(code="outside", name="Other province")
        reports = []
        for authorities in (
            [self.authority],
            [child],
            [grandchild],
            [self.authority, child],
            [outside],
        ):
            report = self._create_report()
            report.relevant_authorities.set(authorities)
            reports.append(report)
        return child, outside, reports

    def _authority_filter_page(self, authorities, include, limit=20, offset=0):
        result = self.execute(
            """query($ids: [ID], $include: Boolean, $limit: Int!, $offset: Int!) {
              incidentReports(
                relevantAuthorities_Id_In: $ids
                includeChildAuthorities: $include
                limit: $limit, offset: $offset
              ) { totalCount results { id } }
            }""",
            {
                "ids": [str(authority.pk) for authority in authorities],
                "include": include,
                "limit": limit,
                "offset": offset,
            },
        )
        self.assertIsNone(result.errors, result.errors)
        return result.data["incidentReports"]

    def test_include_child_authorities_expands_recursively_and_paginates_without_duplicates(self):
        _, _, reports = self._authority_hierarchy_reports()
        first = self._authority_filter_page([self.authority], True, limit=2)
        second = self._authority_filter_page([self.authority], True, limit=2, offset=2)
        ids = [item["id"] for page in (first, second) for item in page["results"]]
        self.assertEqual(len(ids), 4)
        self.assertEqual(set(ids), {str(report.pk) for report in reports[:4]})
        self.assertEqual(first["totalCount"], 4)
        self.assertEqual(second["totalCount"], 4)

    def test_unchecked_or_omitted_child_filter_keeps_direct_authority_matches(self):
        _, _, reports = self._authority_hierarchy_reports()
        for include in (False, None):
            with self.subTest(include=include):
                page = self._authority_filter_page([self.authority], include)
                self.assertEqual(
                    {item["id"] for item in page["results"]},
                    {str(reports[0].pk), str(reports[3].pk)},
                )
                self.assertEqual(page["totalCount"], 2)

    def test_child_filter_preserves_authority_scope_for_officers_and_admins(self):
        child, outside, reports = self._authority_hierarchy_reports()
        self.user.authority = child
        self.user.is_superuser = False
        for role in (AuthorityUser.Role.OFFICER, AuthorityUser.Role.ADMIN):
            with self.subTest(role=role):
                self.user.role = role
                self.user.save(update_fields=["authority", "is_superuser", "role"])
                page = self._authority_filter_page([self.authority], True)
                self.assertEqual(
                    {item["id"] for item in page["results"]},
                    {str(report.pk) for report in reports[1:4]},
                )
                self.assertEqual(page["totalCount"], 3)
                page = self._authority_filter_page([outside], True)
                self.assertEqual(page, {"totalCount": 0, "results": []})

    def test_checked_child_filter_with_no_authority_preserves_visible_reports(self):
        _, _, reports = self._authority_hierarchy_reports()
        page = self._authority_filter_page([], True)
        self.assertEqual(
            {item["id"] for item in page["results"]},
            {str(report.pk) for report in reports[:4]},
        )
        self.assertEqual(page["totalCount"], 4)

    def test_multiple_selected_authorities_remain_exact_even_with_checked_default(self):
        _, outside, reports = self._authority_hierarchy_reports()
        page = self._authority_filter_page([self.authority, outside], True)
        self.assertEqual(
            {item["id"] for item in page["results"]},
            {str(reports[0].pk), str(reports[3].pk)},
        )
        self.assertEqual(page["totalCount"], 2)
