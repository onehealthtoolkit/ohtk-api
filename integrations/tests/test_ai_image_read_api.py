from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import Client
from django.urls import resolve
from django.utils import timezone
from django_tenants.test.cases import TenantTestCase
from django_tenants.test.client import TenantClient
from oauth2_provider.models import get_access_token_model, get_application_model

from accounts.models import Authority, AuthorityUser
from integrations.constants import IntegrationScope
from integrations.models import IntegrationActionLog, IntegrationClient
from reports.models import Category, Image, IncidentReport, ReportType


class AIImageReadApiTests(TenantTestCase):
    @classmethod
    def setup_tenant(cls, tenant):
        tenant.name = "Tenant Alpha"

    def setUp(self):
        connection.set_tenant(self.tenant)
        self.client = TenantClient(self.tenant)
        self.authority = Authority.objects.create(code="BKK", name="Bangkok")
        self.reporter = AuthorityUser.objects.create(
            username="reporter",
            authority=self.authority,
        )
        self.category = Category.objects.create(name="animal")
        self.report_type = ReportType.objects.create(
            name="Animal Sick/Death",
            category=self.category,
            definition={},
            published=True,
        )
        self.report_type.authorities.add(self.authority)
        self.report = IncidentReport.objects.create(
            data={"symptom": "sudden death", "token": "private-report-input"},
            reported_by=self.reporter,
            incident_date=timezone.datetime(2026, 6, 2).date(),
            report_type=self.report_type,
        )
        self.report.relevant_authorities.add(self.authority)
        self.small_gif = (
            b"\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x00\x00\x00\x21\xf9\x04"
            b"\x01\x0a\x00\x01\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02"
            b"\x02\x4c\x01\x00\x3b"
        )
        self.application, self.integration_client, self.access_token = (
            self._create_oauth_client(
                "ai-image-client",
                scope_codes=[IntegrationScope.AI_READ_IMAGES],
                token="ai-image-token",
            )
        )

    def test_endpoints_are_exposed_at_versioned_report_image_paths(self):
        list_match = resolve(self._list_url())
        content_match = resolve(
            f"/api/integrations/v1/reports/{self.report.id}/images/"
            "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/content"
        )

        self.assertEqual("integration-report-images", list_match.url_name)
        self.assertEqual("integration-report-image-content", content_match.url_name)

    def test_list_images_returns_metadata_without_public_urls_and_audits(self):
        cover = self._create_image("cover.gif")
        other = self._create_image("other.gif")
        self.report.cover_image = cover
        self.report.save(update_fields=("cover_image",))

        response = self._get(self._list_url())

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual("2026-06-02", payload["schemaVersion"])
        self.assertEqual(str(self.report.id), payload["reportId"])
        self.assertEqual(2, len(payload["images"]))
        self.assertEqual(str(cover.id), payload["images"][0]["id"])
        self.assertTrue(payload["images"][0]["isCover"])
        self.assertEqual(str(other.id), payload["images"][1]["id"])
        self.assertFalse(payload["images"][1]["isCover"])
        for image in payload["images"]:
            self.assertIn("contentType", image)
            self.assertIn("byteSize", image)
            self.assertIn("createdAt", image)
            self.assertEqual(
                f"/api/integrations/v1/reports/{self.report.id}/images/{image['id']}/content",
                image["links"]["content"],
            )
            self.assertNotIn("url", image)
            self.assertNotIn("imageUrl", image)
            self.assertNotIn("file", image)
        self.assertEqual(
            f"/api/integrations/v1/incidents/{self.report.id}",
            payload["links"]["incident"],
        )
        self.assertNotIn("data", payload)
        self.assertNotIn("uploadFiles", payload)

        action_log = IntegrationActionLog.objects.get()
        self.assertEqual("ai.read_images", action_log.action_type)
        self.assertEqual(IntegrationScope.AI_READ_IMAGES, action_log.required_scope)
        self.assertEqual("reports.IncidentReport", action_log.target_type)
        self.assertEqual(str(self.report.id), action_log.target_id)
        self.assertEqual(
            IntegrationActionLog.ResultStatus.ACCEPTED,
            action_log.result_status,
        )
        self.assertEqual(2, action_log.result_summary["response"]["imageCount"])
        self.assertEqual(
            "[REDACTED]",
            action_log.request_headers_summary["Authorization"],
        )

    def test_list_images_empty_list_is_valid(self):
        response = self._get(self._list_url())

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual([], payload["images"])
        self.assertEqual(
            IntegrationActionLog.ResultStatus.ACCEPTED,
            IntegrationActionLog.objects.get().result_status,
        )

    def test_soft_deleted_images_are_not_listed(self):
        image = self._create_image("gone.gif")
        image.delete()

        response = self._get(self._list_url())

        self.assertEqual(200, response.status_code)
        self.assertEqual([], response.json()["images"])

    def test_download_image_content_returns_bytes_and_audits(self):
        image = self._create_image("photo.gif")

        response = self._get(self._content_url(image.id))

        self.assertEqual(200, response.status_code)
        self.assertEqual(self.small_gif, b"".join(response.streaming_content))
        self.assertTrue(response["Content-Type"].startswith("image/"))
        self.assertEqual("private, no-store", response["Cache-Control"])
        action_log = IntegrationActionLog.objects.get()
        self.assertEqual("ai.read_image_content", action_log.action_type)
        self.assertEqual(IntegrationScope.AI_READ_IMAGES, action_log.required_scope)
        self.assertEqual("reports.Image", action_log.target_type)
        self.assertEqual(str(image.id), action_log.target_id)
        self.assertEqual(
            IntegrationActionLog.ResultStatus.ACCEPTED,
            action_log.result_status,
        )
        self.assertEqual(str(self.report.id), action_log.result_summary["response"]["reportId"])

    def test_extensionless_storage_name_sniffs_jpeg_content_type(self):
        # MinIO/S3-style keys often omit extensions; partners still need image/*.
        jpeg_bytes = (
            b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
            b"\xff\xd9"
        )
        image = Image.objects.create(
            file=SimpleUploadedFile(
                "d60732f8-53e0-4c3c-89f9-fdee95b9f5d8",
                jpeg_bytes,
                content_type="application/octet-stream",
            ),
            report=self.report,
        )

        list_response = self._get(self._list_url())
        content_response = self._get(self._content_url(image.id))

        self.assertEqual(200, list_response.status_code)
        listed = list_response.json()["images"][0]
        self.assertEqual(str(image.id), listed["id"])
        self.assertEqual("image/jpeg", listed["contentType"])
        self.assertEqual(200, content_response.status_code)
        self.assertEqual("image/jpeg", content_response["Content-Type"].split(";", 1)[0])
        self.assertEqual(jpeg_bytes, b"".join(content_response.streaming_content))

    def test_extensionless_gif_sniffs_when_upload_content_type_missing(self):
        image = Image.objects.create(
            file=SimpleUploadedFile(
                str(self.report.id),
                self.small_gif,
                # no useful content_type; filename has no extension
            ),
            report=self.report,
        )

        list_response = self._get(self._list_url())
        content_response = self._get(self._content_url(image.id))

        self.assertEqual("image/gif", list_response.json()["images"][0]["contentType"])
        self.assertEqual(
            "image/gif",
            content_response["Content-Type"].split(";", 1)[0],
        )

    def test_explicit_upload_content_type_wins_over_filename_guess(self):
        image = Image.objects.create(
            file=SimpleUploadedFile(
                "photo.bin",
                self.small_gif,
                content_type="image/gif",
            ),
            report=self.report,
        )

        response = self._get(self._list_url())

        self.assertEqual(200, response.status_code)
        self.assertEqual("image/gif", response.json()["images"][0]["contentType"])

    def test_filename_extension_used_when_present(self):
        image = self._create_image("photo.gif")

        response = self._get(self._list_url())

        self.assertEqual(200, response.status_code)
        # SimpleUploadedFile keeps content_type; either path should yield image/gif
        self.assertEqual("image/gif", response.json()["images"][0]["contentType"])
        self.assertEqual(str(image.id), response.json()["images"][0]["id"])

    def test_content_with_mismatched_report_and_image_is_not_found(self):
        other_report = IncidentReport.objects.create(
            data={"symptom": "other"},
            reported_by=self.reporter,
            incident_date=timezone.datetime(2026, 6, 3).date(),
            report_type=self.report_type,
        )
        other_report.relevant_authorities.add(self.authority)
        image = Image.objects.create(
            file=SimpleUploadedFile(
                "other.gif", self.small_gif, content_type="image/gif"
            ),
            report=other_report,
        )

        response = self._get(self._content_url(image.id))

        self.assertEqual(404, response.status_code)
        self.assertEqual("image_not_found", response.json()["error"]["code"])
        action_log = IntegrationActionLog.objects.get()
        self.assertEqual(
            IntegrationActionLog.ResultStatus.REJECTED,
            action_log.result_status,
        )
        self.assertEqual("image_not_found", action_log.result_summary["error"]["code"])

    def test_missing_functional_scope_is_denied_and_audited(self):
        _application, _integration_client, access_token = self._create_oauth_client(
            "ai-no-image-scope",
            scope_codes=[IntegrationScope.AI_READ_REPORT],
            token="ai-no-image-scope-token",
        )

        response = self._get(self._list_url(), token=access_token.token)

        self.assertEqual(403, response.status_code)
        self.assertEqual("scope_denied", response.json()["error"]["code"])
        action_log = IntegrationActionLog.objects.get()
        self.assertEqual(
            IntegrationActionLog.ResultStatus.REJECTED,
            action_log.result_status,
        )
        self.assertEqual("scope_denied", action_log.result_summary["error"]["code"])

    def test_user_bound_oauth_token_is_denied(self):
        _application, _integration_client, access_token = self._create_oauth_client(
            "ai-image-human-token",
            scope_codes=[IntegrationScope.AI_READ_IMAGES],
            token="ai-image-human-token",
            token_user=self.reporter,
        )

        response = self._get(self._list_url(), token=access_token.token)

        self.assertEqual(403, response.status_code)
        self.assertEqual("service_identity_denied", response.json()["error"]["code"])

    def test_missing_bearer_token_is_not_accepted(self):
        response = self.client.get(self._list_url())

        self.assertEqual(401, response.status_code)
        self.assertEqual("oauth_required", response.json()["error"]["code"])
        self.assertEqual(0, IntegrationActionLog.objects.count())

    def test_public_schema_is_denied_before_integration_authorization(self):
        public_client = Client()
        try:
            response = public_client.get(
                self._list_url(),
                HTTP_AUTHORIZATION=f"Bearer {self.access_token.token}",
            )
        finally:
            connection.set_tenant(self.tenant)

        self.assertEqual(403, response.status_code)
        self.assertEqual("tenant_denied", response.json()["error"]["code"])
        self.assertEqual(0, IntegrationActionLog.objects.count())

    def test_missing_incident_is_rejected_and_audited(self):
        missing_report_id = "22222222-2222-2222-2222-222222222222"
        response = self._get(f"/api/integrations/v1/reports/{missing_report_id}/images")

        self.assertEqual(404, response.status_code)
        self.assertEqual("incident_not_found", response.json()["error"]["code"])
        action_log = IntegrationActionLog.objects.get()
        self.assertEqual(missing_report_id, action_log.target_id)
        self.assertEqual(
            "incident_not_found",
            action_log.result_summary["error"]["code"],
        )

    def _create_image(self, name):
        return Image.objects.create(
            file=SimpleUploadedFile(name, self.small_gif, content_type="image/gif"),
            report=self.report,
        )

    def _create_oauth_client(self, code, scope_codes, token, token_user=None):
        application_model = get_application_model()
        application = application_model.objects.create(
            name=code,
            user=None,
            client_type=application_model.CLIENT_CONFIDENTIAL,
            authorization_grant_type=application_model.GRANT_CLIENT_CREDENTIALS,
        )
        integration_client = IntegrationClient.objects.create(
            name=code,
            code=code,
            integration_type=IntegrationClient.IntegrationType.AI_ASSISTANT,
            oauth_application=application,
            scope_codes=scope_codes,
        )
        access_token_model = get_access_token_model()
        access_token = access_token_model.objects.create(
            user=token_user,
            token=token,
            application=application,
            expires=timezone.now() + timedelta(hours=1),
            scope="",
        )
        return application, integration_client, access_token

    def _get(self, url, token=None):
        return self.client.get(
            url,
            HTTP_AUTHORIZATION=f"Bearer {token or self.access_token.token}",
        )

    def _list_url(self):
        return f"/api/integrations/v1/reports/{self.report.id}/images"

    def _content_url(self, image_id):
        return (
            f"/api/integrations/v1/reports/{self.report.id}/images/{image_id}/content"
        )
