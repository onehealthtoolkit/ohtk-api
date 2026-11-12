"""IDP-0: executable compatibility baseline before adding safe replay.

Uploads currently require login, including uploads to another reporter's parent.
Keep that access contract; this work must not invent a reporter-only ACL. Replay
must additionally verify the concrete parent binding before returning a resource.
Legacy observation images can carry a local reportId, resolved via form_data.
"""
import json
import tempfile
import uuid
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils.timezone import now
from graphql_jwt.testcases import JSONWebTokenClient

from accounts.models import AuthorityUser
from observations.models import (
    Definition,
    MonitoringDefinition,
    MonitoringRecord,
    RecordImage,
    RecordUploadFile,
    SubjectRecord,
)
from reports.models import FollowUpReport, Image, IncidentReport, UploadFile
from reports.tests.base_testcase import BaseTestCase

GIF = (
    b"GIF89a\x01\x00\x01\x00\x00\x00\x00!\xf9\x04"
    b"\x01\x0a\x00\x01\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02"
    b"\x02L\x01\x00;"
)


class SubmissionFixture:
    client_class = JSONWebTokenClient

    def setUp(self):
        self.enqueue_mock = self.enterContext(patch("celery.app.task.Task.apply_async"))
        media = self.enterContext(tempfile.TemporaryDirectory(prefix="idp-contract-"))
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
                THUMBNAIL_DEFAULT_STORAGE="django.core.files.storage.FileSystemStorage",
                CHANNEL_LAYERS={
                    "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}
                },
            )
        )
        super().setUp()
        BaseTestCase.setUp(self)
        self.client = JSONWebTokenClient()
        self.client.authenticate(self.jatujak_reporter)
        self.incident = IncidentReport.objects.create(
            data={},
            reported_by=self.user,
            incident_date=now(),
            report_type=self.mers_report_type,
        )
        self.followup = FollowUpReport.objects.create(
            data={},
            reported_by=self.user,
            report_type=self.mers_report_type,
            incident=self.incident,
        )
        self.definition = Definition.objects.create(
            name="IDP",
            register_form_definition={},
            title_template="",
            description_template="",
            identity_template="",
        )
        self.monitoring_definition = MonitoringDefinition.objects.create(
            definition=self.definition,
            name="IDP monitoring",
            form_definition={},
            title_template="",
            description_template="",
        )
        self.subject = SubjectRecord.objects.create(
            form_data={},
            definition=self.definition,
            reported_by=self.user,
        )
        self.monitoring = MonitoringRecord.objects.create(
            form_data={},
            monitoring_definition=self.monitoring_definition,
            subject=self.subject,
            reported_by=self.user,
        )

    @property
    def parents(self):
        return (self.incident, self.followup, self.subject, self.monitoring)

    def upload(
        self,
        parent,
        *,
        image=False,
        attachment_id="omit",
        cover="omit",
        legacy=False,
        request_parent_id=None,
        authenticated=True,
        client=None,
    ):
        client = client or self.client
        report = isinstance(parent, (IncidentReport, FollowUpReport))
        mutation = (
            ("submitImage" if image else "submitUploadFile")
            if report or legacy
            else ("submitRecordImage" if image else "submitRecordUploadFile")
        )
        parent_arg = "reportId" if report or legacy else "recordId"
        args = [f"{parent_arg}: $parentId"]
        variable_defs = ["$upload: Upload!", "$parentId: UUID!"]
        variables = {"parentId": str(request_parent_id or parent.pk)}
        if image and not report and not legacy:
            args.append(
                f'recordType: {"subject" if isinstance(parent, SubjectRecord) else "monitoring"}'
            )
        args.append(f'{"image" if image else "file"}: $upload')
        if attachment_id != "omit":
            args.append(f'{"imageId" if image else "fileId"}: $attachmentId')
            variable_defs.append("$attachmentId: UUID")
            variables["attachmentId"] = (
                None if attachment_id is None else str(attachment_id)
            )
        if cover != "omit":
            args.append("isCover: " + json.dumps(cover))
        fields = "id file thumbnail imageUrl" if image else "id file fileUrl fileType"
        query = f'mutation({", ".join(variable_defs)}) {{ {mutation}({", ".join(args)}) {{ {fields} }} }}'
        file = SimpleUploadedFile(
            "idp.gif" if image else "idp.txt",
            GIF if image else b"IDP baseline text\n",
            content_type="image/gif" if image else "text/plain",
        )
        if not authenticated:
            client.logout()
        variables["upload"] = file
        result = client.execute(query, variables)
        return result, mutation

    def assert_upload(self, parent, **kwargs):
        result, mutation = self.upload(parent, **kwargs)
        self.assertIsNone(result.errors, result.errors)
        payload = result.data[mutation]
        self.assertTrue(payload["id"])
        self.assertTrue(payload["file"])
        return payload


class SubmissionContractTests(SubmissionFixture, TestCase):
    def test_first_upload_accepts_omitted_null_and_explicit_id_for_every_parent(self):
        for parent in self.parents:
            for image in (False, True):
                for attachment_id in ("omit", None, uuid.uuid4()):
                    with self.subTest(
                        parent=type(parent).__name__, image=image, id=attachment_id
                    ):
                        payload = self.assert_upload(
                            parent, image=image, attachment_id=attachment_id
                        )
                        if attachment_id not in ("omit", None):
                            self.assertEqual(str(attachment_id), payload["id"])
                        if image:
                            self.assertEqual(payload["file"], payload["imageUrl"])
                            self.assertTrue(payload["thumbnail"])
                        else:
                            self.assertEqual(payload["file"], payload["fileUrl"])
                            self.assertEqual("text/plain", payload["fileType"])

    def test_uploads_preserve_reporter_officer_admin_and_superuser_access(self):
        actors = [self.user, self.jatujak_reporter]
        for role in (AuthorityUser.Role.OFFICER, AuthorityUser.Role.ADMIN):
            actors.append(
                AuthorityUser.objects.create(
                    username=f"idp-{role}",
                    authority=self.jatujak,
                    role=role,
                )
            )
        for actor in actors:
            self.client.authenticate(actor)
            for parent in self.parents:
                for image in (False, True):
                    with self.subTest(
                        actor=actor.username, parent=type(parent).__name__, image=image
                    ):
                        self.assert_upload(
                            parent, image=image, attachment_id=uuid.uuid4()
                        )

    def test_anonymous_uploads_rejected_without_creating_attachment(self):
        for parent in self.parents:
            for image in (False, True):
                result, _ = self.upload(parent, image=image, authenticated=False)
                self.assertIsNotNone(result.errors)
        for model in (Image, UploadFile, RecordImage, RecordUploadFile):
            self.assertEqual(0, model.objects.count())

    def test_cover_false_null_and_omitted_preserve_existing_cover(self):
        for parent in self.parents:
            image = self.assert_upload(parent, image=True)
            type(parent).objects.filter(pk=parent.pk).update(cover_image_id=image["id"])
            for value in (False, "omit", None):
                self.assert_upload(parent, image=True, cover=value)
                parent.refresh_from_db()
                self.assertEqual(image["id"], str(parent.cover_image_id))

    def test_cover_true_false_and_omitted_keep_first_upload_behavior(self):
        for parent in self.parents:
            cover = self.assert_upload(parent, image=True, cover=True)
            for value in (False, "omit", None):
                self.assert_upload(parent, image=True, cover=value)
                parent.refresh_from_db()
                self.assertEqual(cover["id"], str(parent.cover_image_id))

    def test_legacy_subject_image_resolves_local_report_id_via_form_data(self):
        image_id = uuid.uuid4()
        self.subject.form_data = {"house_front": {str(image_id): {}}}
        self.subject.save()
        payload = self.assert_upload(
            self.subject,
            image=True,
            legacy=True,
            request_parent_id=uuid.uuid4(),
            attachment_id=image_id,
        )
        self.assertEqual(self.subject, RecordImage.objects.get(pk=payload["id"]).record)

    def test_legacy_monitoring_image_resolves_local_report_id_via_form_data(self):
        image_id = uuid.uuid4()
        self.monitoring.form_data = {"deploy_image": {str(image_id): {}}}
        self.monitoring.save()
        payload = self.assert_upload(
            self.monitoring,
            image=True,
            legacy=True,
            request_parent_id=uuid.uuid4(),
            attachment_id=image_id,
        )
        self.assertEqual(
            self.monitoring, RecordImage.objects.get(pk=payload["id"]).record
        )

    def test_existing_image_replay_keeps_a_later_cover_selection(self):
        image_id = uuid.uuid4()
        first = self.assert_upload(
            self.incident, image=True, attachment_id=image_id, cover=True
        )
        later = self.assert_upload(self.incident, image=True, cover=True)
        replay = self.assert_upload(
            self.incident, image=True, attachment_id=image_id, cover=True
        )
        self.assertEqual(first, replay)
        self.incident.refresh_from_db()
        self.assertEqual(later["id"], str(self.incident.cover_image_id))
        self.assertEqual(2, Image.objects.count())
