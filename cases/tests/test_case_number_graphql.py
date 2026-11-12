from datetime import date
from uuid import uuid4

from cases.models import Case
from cases.tests.base_testcase import BaseTestCase
from reports.models import IncidentReport


class CaseNumberGraphQLTests(BaseTestCase):
    def execute(self, query, variables=None):
        result = self.client.execute(query, variables or {})
        self.assertIsNone(result.errors, result.errors)
        return result.data

    def test_promotion_uses_case_creation_year_and_preserves_report_uuid(self):
        IncidentReport.objects.filter(pk=self.mers_report.pk).update(
            incident_date=date(2000, 1, 1)
        )
        data = self.execute(
            """mutation($id: UUID!) {
              promoteToCase(reportId: $id) {
                case { id caseNumber } report { id caseId caseNumber }
              }
            }""",
            {"id": str(self.mers_report.pk)},
        )["promoteToCase"]
        case = Case.objects.get(pk=data["case"]["id"])
        self.assertEqual(data["case"]["caseNumber"], case.case_number)
        self.assertFalse(case.case_number.startswith("2000-"))
        self.assertEqual(data["report"]["caseNumber"], case.case_number)
        self.assertEqual(data["report"]["caseId"], str(case.pk))
        self.assertEqual(data["report"]["id"], str(self.mers_report.pk))
        again = Case.promote_from_incident_report(self.mers_report.pk)
        self.assertEqual(again.pk, case.pk)
        self.assertEqual(again.case_number, case.case_number)

    def test_case_list_detail_and_exact_search_keep_uuid_and_pagination(self):
        case = Case.promote_from_incident_report(self.mers_report.pk)
        other = Case.promote_from_incident_report(self.dengue_report.pk)
        data = self.execute(
            """query($q: String) {
              casesQuery(q: $q, limit: 1, offset: 0) { results { id caseNumber } }
            }""",
            {"q": "  " + case.case_number + "  "},
        )
        self.assertEqual(
            data["casesQuery"]["results"],
            [{"id": str(case.pk), "caseNumber": case.case_number}],
        )
        detail = self.execute(
            """query($id: UUID!) { caseGet(id: $id) { id caseNumber } }""",
            {"id": str(other.pk)},
        )["caseGet"]
        self.assertEqual(detail, {"id": str(other.pk), "caseNumber": other.case_number})

    def test_search_stays_within_existing_authority_scope(self):
        visible = Case.promote_from_incident_report(self.dengue_report_jatujak.pk)
        hidden = Case.promote_from_incident_report(self.mers_report.pk)
        self.client.authenticate(self.jatujak_reporter)
        for case, expected in ((visible, [str(visible.pk)]), (hidden, [])):
            data = self.execute(
                "query($q: String) { casesQuery(q: $q) { results { id } } }",
                {"q": case.case_number},
            )
            self.assertEqual(
                [row["id"] for row in data["casesQuery"]["results"]], expected
            )

    def test_reports_expose_only_linked_visible_case_and_preserve_unlinked_null(self):
        case = Case.promote_from_incident_report(self.mers_report.pk)
        data = self.execute("{ incidentReports { results { id caseId caseNumber } } }")
        rows = {row["id"]: row for row in data["incidentReports"]["results"]}
        self.assertEqual(rows[str(self.mers_report.pk)]["caseNumber"], case.case_number)
        self.assertIsNone(rows[str(self.dengue_report.pk)]["caseNumber"])
        # A stale UUID link must not invent a Case reference.
        IncidentReport.objects.filter(pk=self.dengue_report.pk).update(case_id=uuid4())
        row = self.execute(
            "query($id: ID!) { incidentReport(id: $id) { caseNumber } }",
            {"id": str(self.dengue_report.pk)},
        )["incidentReport"]
        self.assertIsNone(row["caseNumber"])

    def test_report_link_does_not_reveal_case_outside_authority_scope(self):
        hidden = Case.promote_from_incident_report(self.mers_report.pk)
        IncidentReport.objects.filter(pk=self.dengue_report_jatujak.pk).update(
            case_id=hidden.pk
        )
        self.client.authenticate(self.jatujak_reporter)
        row = self.execute(
            "query($id: ID!) { incidentReport(id: $id) { caseNumber } }",
            {"id": str(self.dengue_report_jatujak.pk)},
        )["incidentReport"]
        self.assertIsNone(row["caseNumber"])

    def test_stale_link_to_another_visible_report_has_no_case_number(self):
        unrelated = Case.promote_from_incident_report(self.mers_report.pk)
        IncidentReport.objects.filter(pk=self.dengue_report.pk).update(
            case_id=unrelated.pk
        )
        row = self.execute(
            "query($id: ID!) { incidentReport(id: $id) { caseNumber } }",
            {"id": str(self.dengue_report.pk)},
        )["incidentReport"]
        self.assertIsNone(row["caseNumber"])
