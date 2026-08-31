from datetime import timedelta

from django.db import connection
from django.urls import resolve
from django.utils import timezone
from django_tenants.test.cases import TenantTestCase
from django_tenants.test.client import TenantClient
from oauth2_provider.models import get_access_token_model, get_application_model

from accounts.models import Authority, AuthorityUser
from integrations.constants import IntegrationScope
from integrations.models import IntegrationActionLog, IntegrationClient
from integrations.policy import set_integration_policy
from reports.models import Category, IncidentReport, ReportType
from threads.models import Comment, Thread


class AiCommentReadApiTests(TenantTestCase):
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
            role=AuthorityUser.Role.REPORTER,
        )
        self.owner = AuthorityUser.objects.create(
            username="ai-owner",
            authority=self.authority,
            role=AuthorityUser.Role.ADMIN,
        )
        self.officer = AuthorityUser.objects.create(
            username="V01",
            authority=self.authority,
            role=AuthorityUser.Role.OFFICER,
        )
        self.category = Category.objects.create(name="animal")
        self.report_type = ReportType.objects.create(
            name="Animal Sick/Death",
            category=self.category,
            definition={},
            published=True,
        )
        self.report = IncidentReport.objects.create(
            data={"symptom": "cough"},
            reported_by=self.reporter,
            incident_date=timezone.datetime(2026, 6, 2).date(),
            report_type=self.report_type,
        )
        self.report.relevant_authorities.add(self.authority)
        set_integration_policy(
            integration_enabled=True,
            ai_enabled=True,
            risk_evaluator_enabled=True,
            cluster_detector_enabled=True,
            ai_default_comment_owner_user_id=str(self.owner.id),
            dashboard_risk_window_days=7,
        )
        _, self.integration_client, self.access_token = self._create_oauth_client(
            "comment-read",
            [IntegrationScope.AI_READ_REPORT],
            "comment-read-token",
        )

    def test_get_comments_returns_thread_in_order(self):
        thread = Thread.objects.create()
        self.report.thread = thread
        self.report.save(update_fields=("thread", "updated_at"))
        first = Comment.objects.create(
            thread=thread, body="Officer note", created_by=self.officer
        )
        Comment.objects.create(
            thread=thread, body="AI summary: done", created_by=self.owner
        )

        response = self._get()

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual("2026-08-31", payload["schemaVersion"])
        self.assertEqual(str(self.report.id), payload["reportId"])
        self.assertEqual(2, len(payload["comments"]))
        self.assertEqual(str(first.id), payload["comments"][0]["id"])
        self.assertEqual("Officer note", payload["comments"][0]["body"])
        self.assertEqual("V01", payload["comments"][0]["authorUsername"])
        self.assertFalse(payload["comments"][0]["isAiOwner"])
        self.assertEqual([], payload["comments"][0]["attachments"])
        self.assertTrue(payload["comments"][1]["isAiOwner"])
        action_log = IntegrationActionLog.objects.get()
        self.assertEqual("ai.read_comments", action_log.action_type)
        self.assertEqual(IntegrationScope.AI_READ_REPORT, action_log.required_scope)

    def test_get_comments_empty_thread_and_missing_report(self):
        empty = self._get()
        self.assertEqual(200, empty.status_code)
        self.assertEqual([], empty.json()["comments"])

        missing = self._get(
            url="/api/integrations/v1/reports/11111111-1111-1111-1111-111111111111/comments"
        )
        self.assertEqual(404, missing.status_code)
        self.assertEqual("incident_not_found", missing.json()["error"]["code"])

    def test_get_comments_requires_scope_and_oauth(self):
        match = resolve(self._url())
        self.assertEqual("integration-report-comments", match.url_name)

        unauth = self.client.get(self._url())
        self.assertEqual(401, unauth.status_code)

        _, _, create_token = self._create_oauth_client(
            "comment-write-only",
            [IntegrationScope.AI_CREATE_COMMENT],
            "comment-write-token",
        )
        denied = self._get(token=create_token.token)
        self.assertEqual(403, denied.status_code)
        self.assertEqual("scope_denied", denied.json()["error"]["code"])

    def _create_oauth_client(self, code, scope_codes, token):
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
            user=None,
            token=token,
            application=application,
            expires=timezone.now() + timedelta(hours=1),
            scope="",
        )
        return application, integration_client, access_token

    def _get(self, token=None, url=None):
        return self.client.get(
            url or self._url(),
            HTTP_AUTHORIZATION=f"Bearer {token or self.access_token.token}",
        )

    def _url(self):
        return f"/api/integrations/v1/reports/{self.report.id}/comments"
