from django.core.exceptions import ValidationError
from django.utils import timezone
from graphql_jwt.testcases import JSONWebTokenClient

from accounts.models import AuthorityUser
from cases.models import Case
from cases.services.case_close import close_case, validate_close_payload
from cases.tests.base_testcase import BaseTestCase


class CaseCloseServiceTestCase(BaseTestCase):
    client_class = JSONWebTokenClient

    def setUp(self):
        super().setUp()
        self.client.authenticate(self.user)
        self.case = Case.promote_from_incident_report(self.mers_report.id)

    def test_validate_empty_definition_allows_any_payload(self):
        cleaned = validate_close_payload(None, {"test_result": "x"}, source="officer")
        self.assertEqual({"test_result": "x"}, cleaned)

    def test_validate_lahis_schema_requires_fields(self):
        definition = {
            "version": 1,
            "fields": [
                {
                    "id": "test_result",
                    "type": "text",
                    "requiredOn": ["officer"],
                },
                {
                    "id": "stamp_out",
                    "type": "species_counts",
                    "requiredOn": ["officer"],
                },
            ],
        }
        with self.assertRaises(ValidationError):
            validate_close_payload(definition, {}, source="officer")
        with self.assertRaises(ValidationError):
            validate_close_payload(
                definition, {"test_result": "ok"}, source="officer"
            )
        cleaned = validate_close_payload(
            definition,
            {"test_result": " Lab ", "stamp_out": {"Cattle": 2}},
            source="officer",
        )
        self.assertEqual("Lab", cleaned["test_result"])
        self.assertEqual({"Cattle": 2}, cleaned["stamp_out"])
        # system ignores required officer fields
        self.assertEqual(
            {},
            validate_close_payload(
                definition, {"test_result": "x"}, source="system"
            ),
        )

    def test_close_case_officer_without_definition(self):
        close_case(
            self.case,
            source=Case.CloseSource.OFFICER,
            actor=self.user,
            payload={"test_result": "done"},
        )
        self.case.refresh_from_db()
        self.assertTrue(self.case.is_finished)
        self.assertIsNotNone(self.case.stopped_at)
        self.assertEqual(Case.CloseSource.OFFICER, self.case.close_source)
        self.assertEqual(self.user.pk, self.case.closed_by_id)
        self.assertEqual("done", self.case.test_result)
        self.assertEqual({"test_result": "done"}, self.case.close_payload)

    def test_close_case_rejects_second_close(self):
        close_case(
            self.case,
            source=Case.CloseSource.OFFICER,
            actor=self.user,
            payload={},
        )
        with self.assertRaises(ValidationError):
            close_case(
                self.case,
                source=Case.CloseSource.OFFICER,
                actor=self.user,
                payload={},
            )

    def test_close_case_system_empty_payload(self):
        self.mers_report_type.close_definition = {
            "version": 1,
            "fields": [
                {"id": "test_result", "type": "text", "requiredOn": ["officer"]},
            ],
        }
        self.mers_report_type.save(update_fields=["close_definition"])
        close_case(self.case, source=Case.CloseSource.SYSTEM, actor=None, payload={})
        self.case.refresh_from_db()
        self.assertEqual(Case.CloseSource.SYSTEM, self.case.close_source)
        self.assertIsNone(self.case.closed_by_id)
        self.assertEqual({}, self.case.close_payload)

    def test_admin_case_close_mutation(self):
        mutation = """
        mutation adminCaseClose($caseId: UUID!, $payload: GenericScalar) {
          adminCaseClose(caseId: $caseId, payload: $payload) {
            result {
              id
              isFinished
              closeSource
              testResult
              closePayload
              stoppedAt
            }
          }
        }
        """
        result = self.client.execute(
            mutation,
            {
                "caseId": str(self.case.id),
                "payload": {"test_result": "Closed via GQL"},
            },
        )
        self.assertIsNone(result.errors, msg=result.errors)
        data = result.data["adminCaseClose"]["result"]
        self.assertTrue(data["isFinished"])
        self.assertEqual("officer", data["closeSource"])
        self.assertEqual("Closed via GQL", data["testResult"])
        self.assertIsNotNone(data["stoppedAt"])

    def test_admin_case_test_result_writes_payload(self):
        mutation = """
        mutation adminCaseTestResultUpdate($caseId: UUID!, $testResult: String!) {
          adminCaseTestResultUpdate(caseId: $caseId, testResult: $testResult) {
            result { id testResult closePayload }
          }
        }
        """
        result = self.client.execute(
            mutation,
            {"caseId": str(self.case.id), "testResult": "draft note"},
        )
        self.assertIsNone(result.errors, msg=result.errors)
        self.case.refresh_from_db()
        self.assertEqual("draft note", self.case.test_result)
        self.assertEqual({"test_result": "draft note"}, self.case.close_payload)

    def test_reporter_cannot_close(self):
        reporter = AuthorityUser.objects.create(
            username="close-rep",
            authority=self.thailand,
            role=AuthorityUser.Role.REPORTER,
        )
        self.client.authenticate(reporter)
        mutation = """
        mutation adminCaseClose($caseId: UUID!) {
          adminCaseClose(caseId: $caseId) { result { id } }
        }
        """
        result = self.client.execute(mutation, {"caseId": str(self.case.id)})
        self.assertIsNotNone(result.errors)
        self.case.refresh_from_db()
        self.assertFalse(self.case.is_finished)

    def test_forward_state_to_stop_sets_stopped_at(self):
        # transition1 goes step1 -> step2 (not stop); transition2 step2 -> step3 stop
        mutation = """
            mutation forwardState($caseId: ID!, $transitionId: ID!, $formData: GenericScalar) {
              forwardState(caseId: $caseId, transitionId: $transitionId, formData: $formData) {
                result { id }
              }
            }
        """
        r1 = self.client.execute(
            mutation,
            {
                "caseId": str(self.case.id),
                "transitionId": self.transition1.id,
                "formData": {},
            },
        )
        self.assertIsNone(r1.errors, msg=r1.errors)
        r2 = self.client.execute(
            mutation,
            {
                "caseId": str(self.case.id),
                "transitionId": self.transition2.id,
                "formData": {"test_result": "via transition"},
            },
        )
        self.assertIsNone(r2.errors, msg=r2.errors)
        self.case.refresh_from_db()
        self.assertTrue(self.case.is_finished)
        self.assertIsNotNone(self.case.stopped_at)
        self.assertEqual(Case.CloseSource.OFFICER, self.case.close_source)
        self.assertEqual("via transition", self.case.test_result)
