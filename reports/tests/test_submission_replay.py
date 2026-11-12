from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
import uuid
import tempfile
from unittest.mock import patch

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from graphql import GraphQLError
from common.submissions import submit_attachment
from django.db import (
    IntegrityError,
    close_old_connections,
    connections,
    connection,
    transaction,
)
from django.test import TestCase, TransactionTestCase, override_settings
from graphql_jwt.testcases import JSONWebTokenClient

from accounts.models import User
from observations.models import RecordImage, RecordUploadFile
from reports.models import FollowUpReport, UploadFile
from reports.tests.test_submission_contract import SubmissionFixture


class FileReplayTests(SubmissionFixture, TestCase):
    def test_replay_returns_original_metadata_without_storage_write(self):
        for parent in self.parents:
            with self.subTest(parent=type(parent).__name__):
                attachment_id = uuid.uuid4()
                first = self.assert_upload(parent, attachment_id=attachment_id)
                files_before = set(Path(settings.MEDIA_ROOT).rglob("*"))
                with patch(
                    "django.core.files.storage.FileSystemStorage._save",
                    side_effect=AssertionError("Replay wrote storage"),
                ):
                    second = self.assert_upload(parent, attachment_id=attachment_id)
                self.assertEqual(first, second)
                self.assertEqual(
                    files_before, set(Path(settings.MEDIA_ROOT).rglob("*"))
                )
                attachment = parent.upload_files.get(pk=attachment_id)
                with attachment.file.open("rb") as stored:
                    self.assertEqual(b"IDP baseline text\n", stored.read())

    def test_same_uuid_wrong_parent_or_parent_type_is_conflict(self):
        attachment_id = uuid.uuid4()
        self.assert_upload(self.incident, attachment_id=attachment_id)
        same_uuid_other_type = FollowUpReport.objects.create(
            id=self.incident.id,
            data={},
            incident=self.incident,
            report_type=self.mers_report_type,
            reported_by=self.user,
        )
        result, _ = self.upload(self.followup, attachment_id=attachment_id)
        self.assertEqual("SUBMISSION_CONFLICT", result.errors[0].extensions["code"])
        # The legacy API resolves an ambiguous UUID to IncidentReport first.
        # Exercise the concrete-type guard directly; do not change that routing.
        with self.assertRaises(GraphQLError) as error:
            submit_attachment(
                UploadFile,
                same_uuid_other_type,
                "report",
                SimpleUploadedFile("idp.txt", b"text"),
                attachment_id,
            )
        self.assertEqual("SUBMISSION_CONFLICT", error.exception.extensions["code"])
        self.assertEqual(1, UploadFile.objects.count())

    def test_soft_deleted_ids_are_not_reused(self):
        for parent, model in (
            (self.incident, UploadFile),
            (self.subject, RecordUploadFile),
        ):
            attachment_id = uuid.uuid4()
            self.assert_upload(parent, attachment_id=attachment_id)
            model.objects.get(pk=attachment_id).delete()
            result, _ = self.upload(parent, attachment_id=attachment_id)
            self.assertEqual("SUBMISSION_CONFLICT", result.errors[0].extensions["code"])
            self.assertEqual(1, model._base_manager.filter(pk=attachment_id).count())
            self.assertFalse(model.objects.filter(pk=attachment_id).exists())

    def test_database_failure_removes_only_attempt_owned_file(self):
        accepted = self.assert_upload(self.incident)
        before = {p for p in Path(settings.MEDIA_ROOT).rglob("*") if p.is_file()}
        with patch.object(
            UploadFile,
            "_do_insert",
            side_effect=IntegrityError("injected insert failure"),
        ):
            result, _ = self.upload(self.incident, attachment_id=uuid.uuid4())
        self.assertIsNotNone(result.errors)
        self.assertEqual(
            before, {p for p in Path(settings.MEDIA_ROOT).rglob("*") if p.is_file()}
        )
        self.assertEqual(accepted["id"], str(UploadFile.objects.get().pk))

    def test_size_and_type_rejections_do_not_create_files(self):
        with override_settings(UPLOAD_FILE_MAX_SIZE=2):
            for parent in self.parents:
                result, _ = self.upload(parent, attachment_id=uuid.uuid4())
                self.assertEqual("File size has exceeded", result.errors[0].message)
        self.assertFalse(any(p.is_file() for p in Path(settings.MEDIA_ROOT).rglob("*")))


class FileConcurrencyTests(SubmissionFixture, TransactionTestCase):
    def concurrent_uploads(
        self, parents, attachment_id, *, image=False, legacy_flags=(False, False)
    ):
        barrier = Barrier(2)
        actor_id = self.jatujak_reporter.pk

        def send(parent, legacy):
            close_old_connections()
            try:
                client = JSONWebTokenClient()
                client.authenticate(User.objects.get(pk=actor_id))
                barrier.wait(timeout=10)
                return self.upload(
                    parent,
                    attachment_id=attachment_id,
                    client=client,
                    image=image,
                    legacy=legacy,
                )[0]
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(send, parent, legacy)
                for parent, legacy in zip(parents, legacy_flags)
            ]
            return [future.result(timeout=20) for future in futures]

    def test_concurrent_replays_return_one_file_for_report_and_observation(self):
        for parent, model in (
            (self.incident, UploadFile),
            (self.subject, RecordUploadFile),
        ):
            attachment_id = uuid.uuid4()
            results = self.concurrent_uploads((parent, parent), attachment_id)
            self.assertTrue(all(result.errors is None for result in results), results)
            self.assertEqual(results[0].data, results[1].data)
            self.assertEqual(1, model.objects.filter(pk=attachment_id).count())
        files = [p for p in Path(settings.MEDIA_ROOT).rglob("*") if p.is_file()]
        self.assertEqual(2, len(files))

    def test_concurrent_conflicting_parent_returns_conflict_without_second_file(self):
        results = self.concurrent_uploads((self.incident, self.followup), uuid.uuid4())
        successes = [result for result in results if result.errors is None]
        failures = [result for result in results if result.errors]
        self.assertEqual(1, len(successes))
        self.assertEqual(1, len(failures))
        self.assertEqual(
            "SUBMISSION_CONFLICT", failures[0].errors[0].extensions["code"]
        )
        self.assertEqual(1, UploadFile.objects.count())
        self.assertEqual(
            1, sum(p.is_file() for p in Path(settings.MEDIA_ROOT).rglob("*"))
        )

    def test_concurrent_images_are_single_resources_across_all_parent_types(self):
        for parent in self.parents:
            image_id = uuid.uuid4()
            results = self.concurrent_uploads((parent, parent), image_id, image=True)
            self.assertTrue(all(result.errors is None for result in results), results)
            self.assertEqual(results[0].data, results[1].data)
            self.assertEqual(1, parent.images.filter(pk=image_id).count())
        self.assertEqual(4, self.enqueue_mock.call_count)

    def test_concurrent_legacy_and_current_observation_images_share_one_lock(self):
        for parent, field in (
            (self.subject, "house_front"),
            (self.monitoring, "deploy_image"),
        ):
            image_id = uuid.uuid4()
            parent.form_data = {field: {str(image_id): {}}}
            parent.save()
            results = self.concurrent_uploads(
                (parent, parent),
                image_id,
                image=True,
                legacy_flags=(True, False),
            )
            self.assertTrue(all(result.errors is None for result in results), results)
            payloads = [next(iter(result.data.values())) for result in results]
            self.assertEqual(*payloads)
            self.assertEqual(1, parent.images.filter(pk=image_id).count())
        self.assertEqual(2, self.enqueue_mock.call_count)


class TenantFileIsolationTests(TransactionTestCase):
    def test_equal_parent_and_file_ids_in_real_tenant_schemas_remain_separate(self):
        from django_tenants.utils import tenant_context
        from observations.models import Definition, SubjectRecord
        from tenants.models import Client

        parent_id, attachment_id = uuid.uuid4(), uuid.uuid4()
        urls = []
        media = self.enterContext(tempfile.TemporaryDirectory(prefix="idp-tenants-"))
        self.enterContext(patch("celery.app.task.Task.apply_async"))
        self.enterContext(
            override_settings(
                MEDIA_ROOT=media,
                STORAGES={
                    "default": {
                        "BACKEND": "django.core.files.storage.FileSystemStorage"
                    },
                    "staticfiles": {
                        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
                    },
                },
            )
        )
        for label in ("a", "b"):
            tenant = Client.objects.create(
                name=f"IDP {label}", schema_name=f"idp_{label}_{uuid.uuid4().hex[:8]}"
            )
            self.addCleanup(tenant.delete, force_drop=True)
            with tenant_context(tenant):
                actor = User.objects.create(username=f"idp-{label}")
                definition = Definition.objects.create(
                    name=f"IDP {label}",
                    register_form_definition={},
                    title_template="",
                    description_template="",
                    identity_template="",
                )
                parent = SubjectRecord.objects.create(
                    id=parent_id,
                    definition=definition,
                    form_data={},
                    reported_by=actor,
                )
                client = JSONWebTokenClient()
                client.authenticate(actor)
                for _ in range(2):
                    result, mutation = SubmissionFixture.upload(
                        self,
                        parent,
                        attachment_id=attachment_id,
                        client=client,
                    )
                    self.assertIsNone(result.errors, result.errors)
                urls.append(result.data[mutation]["fileUrl"])
                self.assertEqual(1, RecordUploadFile.objects.count())
                self.assertEqual(parent, RecordUploadFile.objects.get().record)
        # A deferred task can run after the request's tenant context has exited.
        # Verify the callback re-enters the original real schema and restores it.
        from common.commit_tasks import after_commit

        callback_schemas = []
        with transaction.atomic():
            with tenant_context(tenant):
                after_commit(lambda: callback_schemas.append(connection.schema_name))
            self.assertEqual([], callback_schemas)
        self.assertEqual([tenant.schema_name], callback_schemas)
        self.assertEqual("public", connection.schema_name)
        self.assertNotEqual(*urls)
        self.assertEqual(2, sum(p.is_file() for p in Path(media).rglob("*")))


class ImageReplayTests(SubmissionFixture, TestCase):
    def test_images_replay_without_writing_storage_or_changing_cover(self):
        for parent in self.parents:
            image_id = uuid.uuid4()
            first = self.assert_upload(
                parent, image=True, attachment_id=image_id, cover=True
            )
            later = self.assert_upload(parent, image=True, cover=True)
            with patch(
                "django.core.files.storage.FileSystemStorage._save",
                side_effect=AssertionError("Image replay wrote storage"),
            ):
                replayed = self.assert_upload(
                    parent, image=True, attachment_id=image_id, cover=True
                )
            self.assertEqual(first, replayed)
            parent.refresh_from_db()
            self.assertEqual(later["id"], str(parent.cover_image_id))

    def test_thumbnail_failure_after_acceptance_retries_existing_image(self):
        for parent, target in (
            (
                self.incident,
                "reports.schema.mutations.submit_image_mutation.get_thumbnailer",
            ),
            (
                self.subject,
                "observations.schema.mutations.submit_observation_image_mutation.get_thumbnailer",
            ),
        ):
            image_id = uuid.uuid4()
            with patch(target, side_effect=OSError("injected thumbnail failure")):
                result, _ = self.upload(
                    parent, image=True, attachment_id=image_id, cover=True
                )
            self.assertIsNotNone(result.errors)
            self.assertEqual(1, parent.images.filter(pk=image_id).count())
            self.assert_upload(parent, image=True, attachment_id=image_id, cover=True)
            self.assertEqual(1, parent.images.filter(pk=image_id).count())
            parent.refresh_from_db()
            self.assertEqual(image_id, parent.cover_image_id)

    def test_wrong_parent_and_deleted_image_never_replay(self):
        image_id = uuid.uuid4()
        self.assert_upload(self.incident, image=True, attachment_id=image_id)
        result, _ = self.upload(self.followup, image=True, attachment_id=image_id)
        self.assertEqual("SUBMISSION_CONFLICT", result.errors[0].extensions["code"])
        self.incident.images.get(pk=image_id).delete()
        result, _ = self.upload(self.incident, image=True, attachment_id=image_id)
        self.assertEqual("SUBMISSION_CONFLICT", result.errors[0].extensions["code"])

    def test_legacy_and_current_replay_either_order(self):
        for parent, field in (
            (self.subject, "house_front"),
            (self.monitoring, "deploy_image"),
        ):
            for first_legacy in (False, True):
                image_id = uuid.uuid4()
                parent.form_data = {field: {str(image_id): {}}}
                parent.save()
                first = self.assert_upload(
                    parent, image=True, attachment_id=image_id, legacy=first_legacy
                )
                second = self.assert_upload(
                    parent, image=True, attachment_id=image_id, legacy=not first_legacy
                )
                self.assertEqual(first, second)
                self.assertEqual(1, parent.images.filter(pk=image_id).count())

    def test_legacy_explicit_parent_mismatch_is_rejected_but_local_id_replays(self):
        image_id = uuid.uuid4()
        self.subject.form_data = {"house_front": {str(image_id): {}}}
        self.subject.save()
        self.assert_upload(
            self.subject, image=True, legacy=True, attachment_id=image_id
        )
        # A direct parent ID must not bypass an existing attachment's binding.
        result, _ = self.upload(self.monitoring, image=True, attachment_id=image_id)
        self.assertEqual("SUBMISSION_CONFLICT", result.errors[0].extensions["code"])
        result, _ = self.upload(
            self.monitoring, image=True, legacy=True, attachment_id=image_id
        )
        self.assertEqual("SUBMISSION_CONFLICT", result.errors[0].extensions["code"])
        self.monitoring.form_data = {"deploy_image": {str(image_id): {}}}
        self.monitoring.save()
        # Existing legacy requests resolve the accepted image even if current
        # forms now contain conflicting references. A local ID is not a remote
        # parent binding and must not break a previously accepted upload.
        result, _ = self.upload(
            self.subject,
            image=True,
            legacy=True,
            attachment_id=image_id,
            request_parent_id=uuid.uuid4(),
        )
        self.assertIsNone(result.errors, result.errors)
        self.assertEqual(self.subject, RecordImage.objects.get(pk=image_id).record)

    def test_thumbnail_task_enqueued_only_after_commit_and_not_for_replay(self):
        for parent in (self.incident, self.subject):
            image_id = uuid.uuid4()
            self.enqueue_mock.reset_mock()
            with self.captureOnCommitCallbacks(execute=True):
                self.assert_upload(parent, image=True, attachment_id=image_id)
                self.enqueue_mock.assert_not_called()
            self.enqueue_mock.assert_called_once()
            with self.captureOnCommitCallbacks(execute=True):
                self.assert_upload(parent, image=True, attachment_id=image_id)
            self.enqueue_mock.assert_called_once()

    def test_legacy_subject_replay_survives_form_edits_using_original_form(self):
        image_id = uuid.uuid4()
        # Set the original form as creation does; the fixture starts with {}.
        self.subject.form_data = {"house_front": {str(image_id): {}}}
        self.subject.origin_form_data = dict(self.subject.form_data)
        self.subject.save()
        local_parent_id = uuid.uuid4()
        first = self.assert_upload(
            self.subject,
            image=True,
            legacy=True,
            request_parent_id=local_parent_id,
            attachment_id=image_id,
        )
        self.subject.form_data = {"edited": True}
        self.subject.save()
        replayed = self.assert_upload(
            self.subject,
            image=True,
            legacy=True,
            request_parent_id=local_parent_id,
            attachment_id=image_id,
        )
        self.assertEqual(first, replayed)

    def test_old_mobile_local_id_replays_accepted_image_without_form_reference(self):
        for parent in (self.subject, self.monitoring):
            image_id = uuid.uuid4()
            first = self.assert_upload(parent, image=True, attachment_id=image_id)
            with patch(
                "django.core.files.storage.FileSystemStorage._save",
                side_effect=AssertionError("Legacy replay wrote storage"),
            ):
                replayed = self.assert_upload(
                    parent,
                    image=True,
                    legacy=True,
                    request_parent_id=uuid.uuid4(),
                    attachment_id=image_id,
                )
            self.assertEqual(first, replayed)

    def test_legacy_new_image_still_requires_a_parent_binding(self):
        result, mutation = self.upload(
            self.monitoring,
            image=True,
            legacy=True,
            request_parent_id=uuid.uuid4(),
            attachment_id=uuid.uuid4(),
        )
        self.assertIsNotNone(result.errors)
        self.assertIsNone(result.data[mutation])

    def test_legacy_first_upload_preserves_subject_before_monitoring_lookup(self):
        image_id = uuid.uuid4()
        self.subject.form_data = {"house_front": {str(image_id): {}}}
        self.subject.save()
        self.monitoring.form_data = {"deploy_image": {str(image_id): {}}}
        self.monitoring.save()
        self.assert_upload(
            self.subject,
            image=True,
            legacy=True,
            request_parent_id=uuid.uuid4(),
            attachment_id=image_id,
        )
        self.assertEqual(self.subject, RecordImage.objects.get(pk=image_id).record)
