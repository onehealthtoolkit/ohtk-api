from datetime import timedelta

from django.core.exceptions import ValidationError
from django.utils import timezone
from graphql_jwt.testcases import JSONWebTokenClient

from accounts.models import AuthorityUser, Configuration
from cases.auto_close_config import (
    CASE_AUTO_CLOSE_DAYS_KEY,
    get_case_auto_close_days,
    set_case_auto_close_days,
)
from cases.models import Case
from cases.services.case_close import (
    auto_close_stale_open_cases,
    close_case,
    complete_system_closed_case,
    update_finished_case_close_data,
    validate_close_payload,
)
from cases.tests.base_testcase import BaseTestCase
from reports.models import FollowUpReport
from threads.models import Comment


class CaseCloseServiceTestCase(BaseTestCase):
    client_class = JSONWebTokenClient

    def setUp(self):
        super().setUp()
        self.client.authenticate(self.user)
        self.case = Case.promote_from_incident_report(self.mers_report.id)

    def test_validate_empty_definition_allows_any_payload(self):
        cleaned = validate_close_payload(None, {"test_result": "x"}, source="officer")
        self.assertEqual({"test_result": "x"}, cleaned)

    def test_validate_lahis_opsv_schema_requires_fields(self):
        definition = {
            "id": "animal-close",
            "version": 1,
            "subforms": [],
            "sections": [
                {
                    "label": "Close case",
                    "questions": [
                        {
                            "label": "Test result",
                            "fields": [
                                {
                                    "id": "test_result",
                                    "name": "test_result",
                                    "type": "textarea",
                                    "required": True,
                                }
                            ],
                        },
                        {
                            "label": "Stamped out",
                            "fields": [
                                {
                                    "id": "stamp_out",
                                    "name": "stamp_out",
                                    "type": "integer",
                                    "required": True,
                                    "min": 0,
                                }
                            ],
                        },
                    ],
                }
            ],
        }
        with self.assertRaises(ValidationError):
            validate_close_payload(definition, {}, source="officer")
        with self.assertRaises(ValidationError):
            validate_close_payload(
                definition, {"test_result": "ok"}, source="officer"
            )
        with self.assertRaises(ValidationError):
            validate_close_payload(
                definition,
                {"test_result": "ok", "stamp_out": -1},
                source="officer",
            )
        cleaned = validate_close_payload(
            definition,
            {"test_result": " Lab ", "stamp_out": 3},
            source="officer",
        )
        self.assertEqual("Lab", cleaned["test_result"])
        self.assertEqual(3, cleaned["stamp_out"])
        cleaned2 = validate_close_payload(
            definition,
            {"test_result": "x", "stamp_out": "0"},
            source="officer",
        )
        self.assertEqual(0, cleaned2["stamp_out"])
        self.assertEqual(
            {},
            validate_close_payload(
                definition, {"test_result": "x"}, source="system"
            ),
        )

    def test_validate_legacy_thin_fields_still_works(self):
        definition = {
            "version": 1,
            "fields": [
                {"id": "test_result", "type": "text", "requiredOn": ["officer"]},
            ],
        }
        cleaned = validate_close_payload(
            definition, {"test_result": "ok"}, source="officer"
        )
        self.assertEqual("ok", cleaned["test_result"])

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
        self.assertEqual("close_case", self.case.close_outcome)
        self.assertEqual("done", self.case.close_payload.get("test_result"))
        self.assertEqual("close_case", self.case.close_payload.get("close_outcome"))
        audit = Comment.objects.filter(thread=self.case.thread).order_by("-id").first()
        self.assertIsNotNone(audit)
        self.assertIn("[Case close] Close case", audit.body)
        self.assertIn("test result: done", audit.body)
        self.assertEqual(self.user.pk, audit.created_by_id)

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
            "id": "test-close",
            "version": 1,
            "subforms": [],
            "sections": [
                {
                    "label": "Close",
                    "questions": [
                        {
                            "label": "Test result",
                            "fields": [
                                {
                                    "name": "test_result",
                                    "type": "textarea",
                                    "required": True,
                                }
                            ],
                        }
                    ],
                }
            ],
        }
        self.mers_report_type.save(update_fields=["close_definition"])
        close_case(self.case, source=Case.CloseSource.SYSTEM, actor=None, payload={})
        self.case.refresh_from_db()
        self.assertEqual(Case.CloseSource.SYSTEM, self.case.close_source)
        self.assertIsNone(self.case.closed_by_id)
        self.assertEqual({}, self.case.close_payload)
        self.assertEqual("", self.case.close_outcome or "")
        self.assertEqual("Automatically closed", self.case.status_label)
        audit = Comment.objects.filter(thread=self.case.thread).order_by("-id").first()
        self.assertIsNotNone(audit)
        self.assertIn("[Automatic close]", audit.body)
        self.assertIn("No close data recorded", audit.body)
        self.assertEqual("system", audit.created_by.username)

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

    def test_forward_state_to_stop_does_not_close_case(self):
        """WF1: stop step is workflow finished only — not case lifecycle close."""
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
        self.assertFalse(self.case.is_finished)
        self.assertIsNone(self.case.stopped_at)
        self.assertEqual("", self.case.close_source)
        # workflow tracking still updates label to stop step name
        self.assertEqual(self.step3.name, self.case.status_label)

    def test_admin_false_positive_does_not_merge_draft_payload(self):
        self.case.set_test_result("stale lab draft")
        self.case.save(update_fields=["close_payload", "updated_at"])
        mutation = """
        mutation adminCaseClose($caseId: UUID!, $payload: GenericScalar, $outcome: String) {
          adminCaseClose(caseId: $caseId, payload: $payload, outcome: $outcome) {
            result { id closeOutcome closePayload testResult }
          }
        }
        """
        result = self.client.execute(
            mutation,
            {
                "caseId": str(self.case.id),
                "outcome": "false_positive",
                "payload": {"reason": "Not a case"},
            },
        )
        self.assertIsNone(result.errors, msg=result.errors)
        data = result.data["adminCaseClose"]["result"]
        self.assertEqual("false_positive", data["closeOutcome"])
        self.assertEqual("Not a case", data["closePayload"].get("reason"))
        self.assertNotIn("test_result", data["closePayload"])
        self.assertEqual("", data["testResult"])

    def test_false_positive_finish_skips_definition(self):
        self.mers_report_type.close_definition = {
            "id": "req",
            "version": 1,
            "subforms": [],
            "sections": [
                {
                    "label": "Close",
                    "questions": [
                        {
                            "label": "Test result",
                            "fields": [
                                {
                                    "name": "test_result",
                                    "type": "textarea",
                                    "required": True,
                                }
                            ],
                        }
                    ],
                }
            ],
        }
        self.mers_report_type.save(update_fields=["close_definition"])
        close_case(
            self.case,
            source=Case.CloseSource.OFFICER,
            actor=self.user,
            outcome="false_positive",
            payload={"reason": "Not a real outbreak"},
        )
        self.case.refresh_from_db()
        self.assertTrue(self.case.is_finished)
        self.assertEqual(Case.CloseOutcome.FALSE_POSITIVE, self.case.close_outcome)
        self.assertEqual("false_positive", self.case.close_payload.get("close_outcome"))
        self.assertEqual("Not a real outbreak", self.case.close_payload.get("reason"))
        self.assertNotIn("test_result", self.case.close_payload)

    def test_close_case_outcome_requires_definition_fields(self):
        self.mers_report_type.close_definition = {
            "id": "req",
            "version": 1,
            "subforms": [],
            "sections": [
                {
                    "label": "Close",
                    "questions": [
                        {
                            "label": "Test result",
                            "fields": [
                                {
                                    "name": "test_result",
                                    "type": "textarea",
                                    "required": True,
                                }
                            ],
                        }
                    ],
                }
            ],
        }
        self.mers_report_type.save(update_fields=["close_definition"])
        self.case.report.report_type.refresh_from_db()
        with self.assertRaises(ValidationError):
            close_case(
                self.case,
                source=Case.CloseSource.OFFICER,
                actor=self.user,
                outcome="close_case",
                payload={},
            )

    def _age_case_activity(self, days_ago: int):
        """Set case + report created_at to now - days_ago (activity clock baseline)."""
        old = timezone.now() - timedelta(days=days_ago)
        Case.objects.filter(pk=self.case.pk).update(created_at=old)
        self.case.report.created_at = old
        self.case.report.save(update_fields=["created_at"])
        self.case.refresh_from_db()
        return old

    def test_get_case_auto_close_days_from_configuration(self):
        Configuration.objects.filter(key=CASE_AUTO_CLOSE_DAYS_KEY).delete()
        self.assertEqual(21, get_case_auto_close_days())
        set_case_auto_close_days(14)
        self.assertEqual(14, get_case_auto_close_days())
        Configuration.objects.filter(key=CASE_AUTO_CLOSE_DAYS_KEY).update(
            value="not-a-number"
        )
        self.assertEqual(21, get_case_auto_close_days())

    def test_auto_close_stale_uses_configuration_days(self):
        set_case_auto_close_days(10)
        # Fresh case: not closed
        n = auto_close_stale_open_cases()
        self.case.refresh_from_db()
        self.assertFalse(self.case.is_finished)
        self.assertEqual(0, n)

        # Age report activity past config window
        self._age_case_activity(11)

        n = auto_close_stale_open_cases()
        self.case.refresh_from_db()
        self.assertEqual(1, n)
        self.assertTrue(self.case.is_finished)
        self.assertEqual(Case.CloseSource.SYSTEM, self.case.close_source)
        self.assertEqual("", self.case.close_outcome or "")
        self.assertEqual({}, self.case.close_payload or {})
        self.assertEqual("Automatically closed", self.case.status_label)

    def test_auto_close_explicit_days_overrides_configuration(self):
        set_case_auto_close_days(100)
        self._age_case_activity(5)

        n = auto_close_stale_open_cases(days=3)
        self.case.refresh_from_db()
        self.assertEqual(1, n)
        self.assertTrue(self.case.is_finished)

    def test_auto_close_day_20_stays_open_day_21_closes(self):
        """T1/T2: default 21-day window boundary."""
        set_case_auto_close_days(21)
        self._age_case_activity(20)
        n = auto_close_stale_open_cases()
        self.case.refresh_from_db()
        self.assertEqual(0, n)
        self.assertFalse(self.case.is_finished)

        self._age_case_activity(21)
        n = auto_close_stale_open_cases()
        self.case.refresh_from_db()
        self.assertEqual(1, n)
        self.assertTrue(self.case.is_finished)
        self.assertEqual(Case.CloseSource.SYSTEM, self.case.close_source)
        self.assertEqual("Automatically closed", self.case.status_label)

    def test_auto_close_followup_resets_clock(self):
        """T3: old case + recent follow-up stays open."""
        set_case_auto_close_days(21)
        self._age_case_activity(30)
        fu = FollowUpReport.objects.create(
            reported_by=self.user,
            report_type=self.mers_report_type,
            data={"note": "recent follow-up"},
            incident=self.case.report,
        )
        # Force follow-up activity to 1 day ago (created_at may be auto_now_add)
        recent = timezone.now() - timedelta(days=1)
        FollowUpReport.objects.filter(pk=fu.pk).update(created_at=recent)

        n = auto_close_stale_open_cases()
        self.case.refresh_from_db()
        self.assertEqual(0, n)
        self.assertFalse(self.case.is_finished)

    def test_auto_close_skips_already_officer_finished(self):
        """T4: already closed cases are not re-closed."""
        set_case_auto_close_days(21)
        self._age_case_activity(30)
        close_case(
            self.case,
            source=Case.CloseSource.OFFICER,
            actor=self.user,
            outcome="close_case",
            payload={},
        )
        self.case.refresh_from_db()
        officer_stopped = self.case.stopped_at
        officer_label = self.case.status_label

        n = auto_close_stale_open_cases()
        self.case.refresh_from_db()
        self.assertEqual(0, n)
        self.assertEqual(Case.CloseSource.OFFICER, self.case.close_source)
        self.assertEqual(officer_stopped, self.case.stopped_at)
        self.assertEqual(officer_label, self.case.status_label)

    def test_complete_system_closed_case_fills_layer2(self):
        """CO3b: officer can add test_result/stamp_out after automatic close."""
        definition = {
            "id": "animal-close",
            "version": 1,
            "subforms": [],
            "sections": [
                {
                    "label": "Close case",
                    "questions": [
                        {
                            "label": "Test result",
                            "fields": [
                                {
                                    "id": "test_result",
                                    "name": "test_result",
                                    "type": "textarea",
                                    "required": True,
                                }
                            ],
                        },
                        {
                            "label": "Stamped out",
                            "fields": [
                                {
                                    "id": "stamp_out",
                                    "name": "stamp_out",
                                    "type": "integer",
                                    "required": True,
                                    "min": 0,
                                }
                            ],
                        },
                    ],
                }
            ],
        }
        self.mers_report_type.close_definition = definition
        self.mers_report_type.save(update_fields=["close_definition"])

        close_case(self.case, source=Case.CloseSource.SYSTEM, actor=None, payload={})
        self.case.refresh_from_db()
        stopped = self.case.stopped_at
        self.assertEqual(Case.CloseSource.SYSTEM, self.case.close_source)
        self.assertEqual({}, self.case.close_payload or {})

        complete_system_closed_case(
            self.case,
            actor=self.user,
            payload={"test_result": " Lab + ", "stamp_out": 2},
        )
        self.case.refresh_from_db()
        self.assertTrue(self.case.is_finished)
        self.assertEqual(stopped, self.case.stopped_at)
        self.assertEqual(Case.CloseSource.SYSTEM, self.case.close_source)
        self.assertEqual("close_case", self.case.close_outcome)
        self.assertEqual("Lab +", self.case.test_result)
        self.assertEqual(2, self.case.close_payload.get("stamp_out"))
        self.assertEqual("close_case", self.case.close_payload.get("close_outcome"))
        self.assertEqual(self.user.pk, self.case.closed_by_id)
        self.assertEqual("Automatically closed", self.case.status_label)
        self.assertEqual(1, self.case.close_payload_schema_version)
        # System close + complete each leave an audit comment
        bodies = list(
            Comment.objects.filter(thread=self.case.thread)
            .order_by("id")
            .values_list("body", flat=True)
        )
        self.assertTrue(any("[Automatic close]" in b for b in bodies))
        self.assertTrue(
            any("[Close data] Added after automatic close" in b for b in bodies)
        )
        complete_audit = [
            b for b in bodies if "Added after automatic close" in b
        ][-1]
        self.assertIn("test result: Lab +", complete_audit)
        self.assertIn("stamp out: 2", complete_audit)

    def test_complete_system_closed_rejects_open_and_officer_closed(self):
        with self.assertRaises(ValidationError):
            complete_system_closed_case(
                self.case, actor=self.user, payload={"test_result": "x"}
            )

        close_case(
            self.case,
            source=Case.CloseSource.OFFICER,
            actor=self.user,
            outcome="close_case",
            payload={},
        )
        with self.assertRaises(ValidationError):
            complete_system_closed_case(
                self.case, actor=self.user, payload={"test_result": "x"}
            )

    def test_complete_system_closed_validates_required_fields(self):
        self.mers_report_type.close_definition = {
            "id": "animal-close",
            "version": 1,
            "subforms": [],
            "sections": [
                {
                    "label": "Close",
                    "questions": [
                        {
                            "label": "Test result",
                            "fields": [
                                {
                                    "name": "test_result",
                                    "type": "textarea",
                                    "required": True,
                                }
                            ],
                        }
                    ],
                }
            ],
        }
        self.mers_report_type.save(update_fields=["close_definition"])
        close_case(self.case, source=Case.CloseSource.SYSTEM, actor=None, payload={})
        with self.assertRaises(ValidationError):
            complete_system_closed_case(self.case, actor=self.user, payload={})

    def test_admin_complete_after_auto_close_mutation(self):
        close_case(self.case, source=Case.CloseSource.SYSTEM, actor=None, payload={})
        mutation = """
        mutation adminCaseCompleteAfterAutoClose(
          $caseId: UUID!, $payload: GenericScalar
        ) {
          adminCaseCompleteAfterAutoClose(caseId: $caseId, payload: $payload) {
            result {
              id
              isFinished
              closeSource
              closeOutcome
              testResult
              closePayload
              stoppedAt
              closedBy { id }
            }
          }
        }
        """
        result = self.client.execute(
            mutation,
            {
                "caseId": str(self.case.id),
                "payload": {"test_result": "Late lab note", "stamp_out": 1},
            },
        )
        self.assertIsNone(result.errors, msg=result.errors)
        data = result.data["adminCaseCompleteAfterAutoClose"]["result"]
        self.assertTrue(data["isFinished"])
        self.assertEqual("system", data["closeSource"])
        self.assertEqual("close_case", data["closeOutcome"])
        self.assertEqual("Late lab note", data["testResult"])
        self.assertEqual(1, data["closePayload"].get("stamp_out"))
        self.assertEqual(str(self.user.id), data["closedBy"]["id"])

    def test_reporter_cannot_complete_after_auto_close(self):
        close_case(self.case, source=Case.CloseSource.SYSTEM, actor=None, payload={})
        reporter = AuthorityUser.objects.create(
            username="complete-rep",
            authority=self.thailand,
            role=AuthorityUser.Role.REPORTER,
        )
        self.client.authenticate(reporter)
        mutation = """
        mutation adminCaseCompleteAfterAutoClose($caseId: UUID!) {
          adminCaseCompleteAfterAutoClose(caseId: $caseId) { result { id } }
        }
        """
        result = self.client.execute(mutation, {"caseId": str(self.case.id)})
        self.assertIsNotNone(result.errors)
        self.case.refresh_from_db()
        self.assertEqual({}, self.case.close_payload or {})
        self.assertEqual("", self.case.close_outcome or "")

    def test_superuser_can_update_finished_officer_close_data(self):
        """Superuser may edit Layer2 on officer-finished cases without reopen."""
        close_case(
            self.case,
            source=Case.CloseSource.OFFICER,
            actor=self.user,
            outcome="close_case",
            payload={"test_result": "initial"},
        )
        stopped = self.case.stopped_at
        closed_by_id = self.case.closed_by_id

        update_finished_case_close_data(
            self.case,
            actor=self.user,  # base test user is superuser
            payload={"test_result": "corrected lab", "stamp_out": 4},
        )
        self.case.refresh_from_db()
        self.assertTrue(self.case.is_finished)
        self.assertEqual(stopped, self.case.stopped_at)
        self.assertEqual(Case.CloseSource.OFFICER, self.case.close_source)
        self.assertEqual(closed_by_id, self.case.closed_by_id)
        self.assertEqual("corrected lab", self.case.test_result)
        self.assertEqual(4, self.case.close_payload.get("stamp_out"))
        audit = (
            Comment.objects.filter(thread=self.case.thread)
            .order_by("-id")
            .first()
        )
        self.assertIsNotNone(audit)
        self.assertIn("[Close data] Superuser edit", audit.body)
        self.assertIn("test result: corrected lab", audit.body)
        self.assertIn("stamp out: 4", audit.body)

    def test_non_superuser_cannot_update_finished_close_data(self):
        officer = AuthorityUser.objects.create(
            username="officer-no-su",
            authority=self.thailand,
            role=AuthorityUser.Role.OFFICER,
            is_superuser=False,
        )
        close_case(
            self.case,
            source=Case.CloseSource.OFFICER,
            actor=officer,
            outcome="close_case",
            payload={"test_result": "locked"},
        )
        with self.assertRaises(ValidationError):
            update_finished_case_close_data(
                self.case,
                actor=officer,
                payload={"test_result": "hacked"},
            )
        self.case.refresh_from_db()
        self.assertEqual("locked", self.case.test_result)

    def test_admin_case_close_data_update_mutation_superuser_only(self):
        close_case(
            self.case,
            source=Case.CloseSource.OFFICER,
            actor=self.user,
            outcome="close_case",
            payload={"test_result": "before"},
        )
        mutation = """
        mutation adminCaseCloseDataUpdate($caseId: UUID!, $payload: GenericScalar) {
          adminCaseCloseDataUpdate(caseId: $caseId, payload: $payload) {
            result { id testResult closePayload closeSource isFinished }
          }
        }
        """
        # self.user is superuser
        result = self.client.execute(
            mutation,
            {
                "caseId": str(self.case.id),
                "payload": {"test_result": "after-su"},
            },
        )
        self.assertIsNone(result.errors, msg=result.errors)
        data = result.data["adminCaseCloseDataUpdate"]["result"]
        self.assertEqual("after-su", data["testResult"])
        self.assertEqual("officer", data["closeSource"])
        self.assertTrue(data["isFinished"])

        officer = AuthorityUser.objects.create(
            username="officer-edit-block",
            authority=self.thailand,
            role=AuthorityUser.Role.OFFICER,
            is_superuser=False,
        )
        self.client.authenticate(officer)
        blocked = self.client.execute(
            mutation,
            {
                "caseId": str(self.case.id),
                "payload": {"test_result": "officer-try"},
            },
        )
        self.assertIsNotNone(blocked.errors)
        self.case.refresh_from_db()
        self.assertEqual("after-su", self.case.test_result)

    def test_superuser_can_update_false_positive_reason(self):
        close_case(
            self.case,
            source=Case.CloseSource.OFFICER,
            actor=self.user,
            outcome="false_positive",
            payload={"reason": "noise"},
        )
        update_finished_case_close_data(
            self.case,
            actor=self.user,
            payload={"reason": "mis-classified report"},
        )
        self.case.refresh_from_db()
        self.assertEqual("false_positive", self.case.close_outcome)
        self.assertEqual(
            "mis-classified report", self.case.close_payload.get("reason")
        )
