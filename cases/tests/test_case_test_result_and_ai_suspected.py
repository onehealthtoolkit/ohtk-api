from graphql_jwt.testcases import JSONWebTokenClient

from accounts.models import AuthorityUser
from cases.models import Case
from cases.tests.base_testcase import BaseTestCase
from integrations.services import apply_ai_suspected_from_comment_body


class CaseTestResultAndAiSuspectedTestCase(BaseTestCase):
    client_class = JSONWebTokenClient

    def setUp(self):
        super().setUp()
        self.client.authenticate(self.user)
        self.case = Case.promote_from_incident_report(self.mers_report.id)

    def test_officer_updates_test_result_only(self):
        self.case.report.ai_suspected = "AI says FMD"
        self.case.report.save(update_fields=["ai_suspected"])

        mutation = """
        mutation adminCaseTestResultUpdate($caseId: UUID!, $testResult: String!) {
          adminCaseTestResultUpdate(caseId: $caseId, testResult: $testResult) {
            result {
              id
              testResult
              aiSuspected
            }
          }
        }
        """
        result = self.client.execute(
            mutation,
            {
                "caseId": str(self.case.id),
                "testResult": "Lab confirmed; REF-123",
            },
        )
        self.assertIsNone(result.errors, msg=result.errors)
        data = result.data["adminCaseTestResultUpdate"]["result"]
        self.assertEqual("Lab confirmed; REF-123", data["testResult"])
        self.assertEqual("AI says FMD", data["aiSuspected"])

        self.case.refresh_from_db()
        self.case.report.refresh_from_db()
        self.assertEqual("Lab confirmed; REF-123", self.case.test_result)
        self.assertEqual("AI says FMD", self.case.report.ai_suspected)

    def test_reporter_cannot_update_test_result(self):
        reporter = AuthorityUser.objects.create(
            username="co1-reporter",
            authority=self.thailand,
            role=AuthorityUser.Role.REPORTER,
        )
        self.client.authenticate(reporter)
        mutation = """
        mutation adminCaseTestResultUpdate($caseId: UUID!, $testResult: String!) {
          adminCaseTestResultUpdate(caseId: $caseId, testResult: $testResult) {
            result { id testResult }
          }
        }
        """
        result = self.client.execute(
            mutation,
            {"caseId": str(self.case.id), "testResult": "nope"},
        )
        self.assertIsNotNone(result.errors)
        self.case.refresh_from_db()
        self.assertEqual("", self.case.test_result)

    def test_apply_ai_suspected_from_body_does_not_touch_test_result(self):
        self.case.set_test_result("Officer note kept")
        self.case.save(update_fields=["close_payload"])
        body = "AI assessment: likely Rabies. Decision support only."
        apply_ai_suspected_from_comment_body(report=self.mers_report, body=body)
        self.mers_report.refresh_from_db()
        self.case.refresh_from_db()
        self.assertEqual(body, self.mers_report.ai_suspected)
        self.assertEqual("Officer note kept", self.case.test_result)

    def test_second_ai_body_replaces_ai_suspected(self):
        apply_ai_suspected_from_comment_body(
            report=self.mers_report, body="First AI body"
        )
        apply_ai_suspected_from_comment_body(
            report=self.mers_report, body="Second AI body"
        )
        self.mers_report.refresh_from_db()
        self.assertEqual("Second AI body", self.mers_report.ai_suspected)

    def test_case_get_exposes_fields(self):
        self.mers_report.ai_suspected = "AI text"
        self.mers_report.save(update_fields=["ai_suspected"])
        self.case.set_test_result("Officer text")
        self.case.save(update_fields=["close_payload"])

        query = """
        query caseGet($id: UUID!) {
          caseGet(id: $id) {
            id
            testResult
            aiSuspected
            report { id aiSuspected }
          }
        }
        """
        result = self.client.execute(query, {"id": str(self.case.id)})
        self.assertIsNone(result.errors, msg=result.errors)
        data = result.data["caseGet"]
        self.assertEqual("Officer text", data["testResult"])
        self.assertEqual("AI text", data["aiSuspected"])
        self.assertEqual("AI text", data["report"]["aiSuspected"])
