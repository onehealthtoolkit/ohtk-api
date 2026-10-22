from datetime import date
from uuid import uuid4

from django.contrib.auth.models import AnonymousUser
from django.db import connection
from django.test import RequestFactory
from django.test.utils import CaptureQueriesContext
from django_tenants.test.cases import TenantTestCase
from django_tenants.utils import schema_context, tenant_context
from tenants.models import Client as Tenant

from accounts.models import Authority, AuthorityUser
from cases.models import Case
from cases.services.case_close import close_case, complete_system_closed_case
from podd_api.schema import schema
from reports.models import Category, IncidentReport, ReportType


STATUS_FIELDS = "caseStatus { isFinished closeSource closeOutcome }"


class ReportCaseStatusTests(TenantTestCase):
    @classmethod
    def setup_tenant(cls, tenant):
        tenant.name = "Case status tenant"

    def setUp(self):
        super().setUp()
        self.authority = Authority.objects.create(code="A", name="A")
        self.user = AuthorityUser.objects.create(
            username="vvw", authority=self.authority
        )
        self.report_type = ReportType.objects.create(
            name="Animals",
            category=Category.objects.create(name="Animals"),
            definition={},
            published=True,
        )
        self.request = RequestFactory().post("/graphql/")
        self.request.user = self.user
        # Boundary query should still honor its own authority filter.
        self.authority.boundary_connects.add(self.authority)

    def report(self):
        report = IncidentReport.objects.create(
            reported_by=self.user,
            report_type=self.report_type,
            data={},
            incident_date=date(2026, 10, 22),
            relevant_authority_resolved=True,
        )
        report.relevant_authorities.add(self.authority)
        return report

    def case(self, report):
        case = Case.objects.create(report=report, thread=report.thread)
        IncidentReport.objects.filter(pk=report.pk).update(case_id=case.pk)
        report.case_id = case.pk
        return case

    def execute(self, query):
        result = schema.execute(query, context_value=self.request)
        self.assertIsNone(result.errors, result.errors)
        return result.data

    def assert_reads(self, report, expected):
        for field in (
            "incidentReports",
            "myIncidentReports",
            "boundaryConnectedIncidentReports",
        ):
            with self.subTest(read=field):
                data = self.execute(
                    f"{{ {field}(limit: 20, offset: 0) {{ results {{ id caseId {STATUS_FIELDS} }} }} }}"
                )
                row = next(
                    row for row in data[field]["results"] if row["id"] == str(report.pk)
                )
                self.assertEqual(row["caseStatus"], expected)
                self.assertEqual(
                    row["caseId"], str(report.case_id) if report.case_id else None
                )
        data = self.execute(
            f'{{ incidentReport(id: "{report.pk}") {{ id caseId {STATUS_FIELDS} }} }}'
        )
        self.assertEqual(data["incidentReport"]["caseStatus"], expected)

    def test_no_case_and_open_case(self):
        report = self.report()
        self.assert_reads(report, None)
        self.case(report)
        self.assert_reads(
            report, dict(isFinished=False, closeSource="", closeOutcome="")
        )

    def test_close_transitions_and_late_system_completion_preserve_link_and_history(
        self,
    ):
        for source, outcome in [
            ("officer", "close_case"),
            ("officer", "false_positive"),
            ("system", ""),
        ]:
            with self.subTest(source=source, outcome=outcome):
                report = self.report()
                case = self.case(report)
                close_case(
                    case,
                    source=source,
                    actor=self.user if source == "officer" else None,
                    outcome=outcome or None,
                    payload={"reason": "reviewed"},
                )
                self.assert_reads(
                    report,
                    dict(isFinished=True, closeSource=source, closeOutcome=outcome),
                )
                self.assertTrue(case.thread.comments.exists())
                report.refresh_from_db()
                self.assertEqual(report.case_id, case.pk)
                if source == "system":
                    complete_system_closed_case(
                        case, actor=self.user, payload={"test_result": "done"}
                    )
                    self.assert_reads(
                        report,
                        dict(
                            isFinished=True,
                            closeSource="system",
                            closeOutcome="close_case",
                        ),
                    )

    def test_missing_deleted_mismatched_and_arbitrary_reverse_case_are_unknown(self):
        report = self.report()
        self.case(report)
        # An available reverse case must not substitute for the exact linked UUID.
        IncidentReport.objects.filter(pk=report.pk).update(case_id=uuid4())
        report.refresh_from_db()
        self.assert_reads(report, None)
        other = self.report()
        other_case = self.case(other)
        IncidentReport.objects.filter(pk=report.pk).update(case_id=other_case.pk)
        report.refresh_from_db()
        self.assert_reads(report, None)
        other_case.delete()
        self.assert_reads(other, None)

    def test_lists_keep_existing_authority_and_own_report_scope(self):
        visible = self.report()
        hidden = self.report()
        other = Authority.objects.create(code="B", name="B")
        hidden.relevant_authorities.set([other])
        self.case(hidden)
        for field in (
            "incidentReports",
            "myIncidentReports",
            "boundaryConnectedIncidentReports",
        ):
            data = self.execute(
                f"{{ {field}(limit: 20, offset: 0) {{ results {{ id {STATUS_FIELDS} }} }} }}"
            )
            self.assertEqual(
                [row["id"] for row in data[field]["results"]], [str(visible.pk)]
            )
        another_user = AuthorityUser.objects.create(
            username="other-vvw", authority=self.authority
        )
        IncidentReport.objects.filter(pk=visible.pk).update(reported_by=another_user)
        data = self.execute(
            f"{{ myIncidentReports(limit: 20, offset: 0) {{ results {{ id {STATUS_FIELDS} }} }} }}"
        )
        self.assertEqual(data["myIncidentReports"]["results"], [])

    def test_case_lookup_query_count_is_constant_for_one_and_twenty_reports(self):
        self.case(self.report())
        query = f"{{ incidentReports(limit: 20, offset: 0) {{ results {{ id {STATUS_FIELDS} }} }} }}"
        self.execute(query)  # warm shared content-type and authority caches
        with CaptureQueriesContext(connection) as one:
            self.execute(query)
        for _ in range(19):
            self.case(self.report())
        with CaptureQueriesContext(connection) as twenty:
            data = self.execute(query)
        self.assertEqual(len(data["incidentReports"]["results"]), 20)
        self.assertEqual(len(one), len(twenty))
        case_queries = [q["sql"] for q in twenty if 'FROM "cases_case"' in q["sql"]]
        self.assertEqual(len(case_queries), 1)

    def test_projection_never_resolves_a_case_from_another_tenant(self):
        report = self.report()
        foreign_case_id = uuid4()
        IncidentReport.objects.filter(pk=report.pk).update(case_id=foreign_case_id)
        report.refresh_from_db()
        with schema_context("public"):
            other = Tenant(schema_name="co2c_other", name="Other")
            other.save(verbosity=0)
        try:
            with tenant_context(other):
                category = Category.objects.create(name="Other")
                report_type = ReportType.objects.create(
                    name="Other", category=category, definition={}
                )
                foreign_report = IncidentReport.objects.create(
                    pk=report.pk,
                    report_type=report_type,
                    data={},
                    incident_date=date(2026, 10, 22),
                    relevant_authority_resolved=True,
                )
                Case.objects.create(
                    pk=foreign_case_id,
                    report=foreign_report,
                    is_finished=True,
                    close_source="officer",
                    close_outcome="close_case",
                )
            connection.set_tenant(self.tenant)
            self.assert_reads(report, None)
        finally:
            with schema_context("public"):
                with connection.cursor() as cursor:
                    cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
                other.delete(force_drop=True)
            connection.set_tenant(self.tenant)

    def test_projection_keeps_report_reads_login_required(self):
        report = self.report()
        self.case(report)
        self.request.user = AnonymousUser()
        for field in (
            "incidentReports",
            "myIncidentReports",
            "boundaryConnectedIncidentReports",
        ):
            result = schema.execute(
                f"{{ {field}(limit: 20, offset: 0) {{ results {{ id {STATUS_FIELDS} }} }} }}",
                context_value=self.request,
            )
            self.assertTrue(result.errors)
            self.assertIsNone(result.data[field])
        result = schema.execute(
            f'{{ incidentReport(id: "{report.pk}") {{ {STATUS_FIELDS} }} }}',
            context_value=self.request,
        )
        self.assertTrue(result.errors)
        self.assertIsNone(result.data["incidentReport"])
