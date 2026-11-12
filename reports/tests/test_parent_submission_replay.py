from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import AsyncMock, patch
from types import SimpleNamespace
import uuid

from django.db import IntegrityError, close_old_connections, connections
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from graphql_jwt.testcases import JSONWebTokenClient

from accounts.models import User
from observations.models import SubjectRecord, MonitoringRecord
from reports.models import IncidentReport, FollowUpReport
from threads.models import Thread
from reports.tests.test_submission_contract import SubmissionFixture


class ParentRequests:
    def submit_parent(
        self, kind, submission_id, *, client=None, related=None, data=None
    ):
        client = client or self.client
        data = {} if data is None else data
        fields = {
            "incident": (
                "submitIncidentReport",
                "reportId",
                "$type: UUID!, $date: Date!",
                "reportTypeId: $type, incidentDate: $date",
                {"type": str(self.mers_report_type.pk), "date": "2026-11-05"},
            ),
            "followup": (
                "submitFollowupReport",
                "followupId",
                "$parent: UUID!",
                "incidentId: $parent",
                {"parent": str(related or self.incident.pk)},
            ),
            "subject": (
                "submitObservationSubject",
                "recordId",
                "$definition: Int!",
                "definitionId: $definition",
                {"definition": related or self.definition.pk},
            ),
            "monitoring": (
                "submitObservationSubjectMonitoring",
                "recordId",
                "$definition: Int!, $parent: UUID!",
                "monitoringDefinitionId: $definition, subjectId: $parent",
                {
                    "definition": self.monitoring_definition.pk,
                    "parent": str(related or self.subject.pk),
                },
            ),
        }
        mutation, id_arg, declarations, args, variables = fields[kind]
        variables["data"] = data
        if submission_id != "omit":
            declarations += ", $id: UUID"
            args += f", {id_arg}: $id"
            variables["id"] = None if submission_id is None else str(submission_id)
        query = f"mutation($data: GenericScalar!, {declarations}) {{ {mutation}(data: $data, {args}) {{ result {{ id }} }} }}"
        result = client.execute(query, variables)
        return result


class ReportParentReplayTests(ParentRequests, SubmissionFixture, TestCase):
    def test_report_and_followup_replay_original_submission(self):
        for kind, model in (("incident", IncidentReport), ("followup", FollowUpReport)):
            submission_id = uuid.uuid4()
            first = self.submit_parent(kind, submission_id, data={"value": "first"})
            second = self.submit_parent(kind, submission_id, data={"value": "retry"})
            self.assertIsNone(first.errors, first.errors)
            self.assertIsNone(second.errors, second.errors)
            self.assertEqual(first.data, second.data)
            self.assertEqual(
                {"value": "first"}, model.objects.get(pk=submission_id).data
            )

    def test_omitted_and_null_ids_preserve_server_assigned_ids(self):
        for kind in ("incident", "followup"):
            ids = []
            for value in ("omit", None):
                result = self.submit_parent(kind, value)
                self.assertIsNone(result.errors, result.errors)
                ids.append(next(iter(result.data.values()))["result"]["id"])
            self.assertNotEqual(*ids)

    def test_parent_mismatch_and_deleted_submission_rejected(self):
        submission_id = uuid.uuid4()
        first = self.submit_parent("followup", submission_id)
        self.assertIsNone(first.errors, first.errors)
        result = self.submit_parent("followup", submission_id, related=uuid.uuid4())
        self.assertEqual("SUBMISSION_CONFLICT", result.errors[0].extensions["code"])
        for kind, model in (("incident", IncidentReport), ("followup", FollowUpReport)):
            submission_id = uuid.uuid4()
            self.assertIsNone(self.submit_parent(kind, submission_id).errors)
            model._base_manager.filter(pk=submission_id).update(
                deleted_at=timezone.now()
            )
            result = self.submit_parent(kind, submission_id)
            self.assertEqual("SUBMISSION_CONFLICT", result.errors[0].extensions["code"])

    def test_report_creation_rolls_back_thread_when_insert_fails(self):
        before = Thread.objects.count()
        with patch.object(
            IncidentReport, "_do_insert", side_effect=IntegrityError("injected failure")
        ):
            result = self.submit_parent("incident", uuid.uuid4())
        self.assertIsNotNone(result.errors)
        self.assertEqual(before, Thread.objects.count())

    def test_report_tasks_are_enqueued_after_commit_once(self):
        submission_id = uuid.uuid4()
        self.enqueue_mock.reset_mock()
        with self.captureOnCommitCallbacks(execute=True):
            first = self.submit_parent("incident", submission_id)
            self.assertIsNone(first.errors, first.errors)
            self.enqueue_mock.assert_not_called()
        self.assertEqual(4, self.enqueue_mock.call_count)
        with self.captureOnCommitCallbacks(execute=True):
            replay = self.submit_parent("incident", submission_id)
            self.assertIsNone(replay.errors, replay.errors)
        self.assertEqual(4, self.enqueue_mock.call_count)

    def test_realtime_notifications_wait_for_commit_and_are_not_replayed(self):
        submission_id = uuid.uuid4()
        layer = SimpleNamespace(group_send=AsyncMock())
        mutation = """
            mutation($id: UUID!, $type: UUID!, $data: GenericScalar!, $date: Date!) {
                submitIncidentReport(reportId: $id, reportTypeId: $type,
                    data: $data, incidentDate: $date, incidentInAuthority: true) {
                    result { id }
                }
            }
        """
        variables = {
            "id": str(submission_id),
            "type": str(self.mers_report_type.pk),
            "data": {},
            "date": "2026-11-05",
        }
        with patch(
            "reports.signals.channels.layers.get_channel_layer", return_value=layer
        ):
            with self.captureOnCommitCallbacks(execute=True):
                result = self.client.execute(mutation, variables)
                self.assertIsNone(result.errors, result.errors)
                layer.group_send.assert_not_called()
            calls = layer.group_send.await_count
            self.assertEqual(3, calls)  # Jatujak -> BKK -> Thailand.
            with self.captureOnCommitCallbacks(execute=True):
                replay = self.client.execute(mutation, variables)
                self.assertIsNone(replay.errors, replay.errors)
            self.assertEqual(calls, layer.group_send.await_count)


class ParentConcurrencyDriver(ParentRequests):
    def concurrent_submissions(self, kind, submission_id):
        barrier = Barrier(2)
        actor_id = self.jatujak_reporter.pk

        def send():
            close_old_connections()
            try:
                client = JSONWebTokenClient()
                client.authenticate(User.objects.get(pk=actor_id))
                barrier.wait(timeout=10)
                return self.submit_parent(kind, submission_id, client=client)
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(send) for _ in range(2)]
            return [future.result(timeout=20) for future in futures]


class ReportParentConcurrencyTests(
    ParentConcurrencyDriver, SubmissionFixture, TransactionTestCase
):
    def test_concurrent_report_and_followup_have_one_resource_and_thread(self):
        for kind, model in (("incident", IncidentReport), ("followup", FollowUpReport)):
            before = Thread.objects.count()
            submission_id = uuid.uuid4()
            results = self.concurrent_submissions(kind, submission_id)
            self.assertTrue(all(result.errors is None for result in results), results)
            self.assertEqual(results[0].data, results[1].data)
            self.assertEqual(1, model.objects.filter(pk=submission_id).count())
            self.assertEqual(before + (kind == "incident"), Thread.objects.count())
        self.assertEqual(4, self.enqueue_mock.call_count)


class ObservationParentReplayTests(ParentRequests, SubmissionFixture, TestCase):
    def test_subject_and_monitoring_replay_original_submission(self):
        for kind, model in (
            ("subject", SubjectRecord),
            ("monitoring", MonitoringRecord),
        ):
            submission_id = uuid.uuid4()
            first = self.submit_parent(kind, submission_id, data={"value": "first"})
            second = self.submit_parent(kind, submission_id, data={"value": "retry"})
            self.assertIsNone(first.errors, first.errors)
            self.assertIsNone(second.errors, second.errors)
            self.assertEqual(first.data, second.data)
            self.assertEqual(
                {"value": "first"}, model.objects.get(pk=submission_id).form_data
            )

    def test_old_operations_omitting_or_nulling_new_id_keep_working(self):
        for kind in ("subject", "monitoring"):
            ids = []
            for value in ("omit", None):
                result = self.submit_parent(kind, value)
                self.assertIsNone(result.errors, result.errors)
                ids.append(next(iter(result.data.values()))["result"]["id"])
            self.assertNotEqual(*ids)

    def test_monitoring_replay_does_not_reapply_updates_to_subject(self):
        submission_id = uuid.uuid4()
        result = self.submit_parent(
            "monitoring", submission_id, data={"upd_state": "first"}
        )
        self.assertIsNone(result.errors, result.errors)
        self.subject.refresh_from_db()
        self.assertEqual("first", self.subject.form_data["state"])
        self.subject.form_data["state"] = "later"
        self.subject.save()
        replayed = self.submit_parent(
            "monitoring", submission_id, data={"upd_state": "first"}
        )
        self.assertIsNone(replayed.errors, replayed.errors)
        self.subject.refresh_from_db()
        self.assertEqual("later", self.subject.form_data["state"])

    def test_definition_parent_mismatch_and_deleted_id_are_rejected(self):
        for kind, model in (
            ("subject", SubjectRecord),
            ("monitoring", MonitoringRecord),
        ):
            submission_id = uuid.uuid4()
            self.assertIsNone(self.submit_parent(kind, submission_id).errors)
            wrong = self.definition.pk + 1000 if kind == "subject" else uuid.uuid4()
            result = self.submit_parent(kind, submission_id, related=wrong)
            self.assertEqual("SUBMISSION_CONFLICT", result.errors[0].extensions["code"])
            model._base_manager.filter(pk=submission_id).update(
                deleted_at=timezone.now()
            )
            result = self.submit_parent(kind, submission_id)
            self.assertEqual("SUBMISSION_CONFLICT", result.errors[0].extensions["code"])


class ObservationParentConcurrencyTests(
    ParentConcurrencyDriver, SubmissionFixture, TransactionTestCase
):
    # Reuse the independent-connection request driver, not the production helper.
    def test_concurrent_subject_and_monitoring_return_one_resource(self):
        for kind, model in (
            ("subject", SubjectRecord),
            ("monitoring", MonitoringRecord),
        ):
            submission_id = uuid.uuid4()
            results = self.concurrent_submissions(kind, submission_id)
            self.assertTrue(all(result.errors is None for result in results), results)
            self.assertEqual(results[0].data, results[1].data)
            self.assertEqual(1, model.objects.filter(pk=submission_id).count())
