from unittest import mock

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import connection
from django.test import SimpleTestCase
from django.urls import get_resolver
from django_tenants.test.cases import TenantTestCase
from django_tenants.utils import schema_context
from oauth2_provider.models import get_application_model

from integrations.constants import IntegrationScope
from integrations.exceptions import (
    IntegrationClientDenied,
    IntegrationIdempotencyConflict,
    IntegrationScopeDenied,
    PublicSchemaDenied,
)
from integrations.models import IntegrationClient, RiskAssessment, WebhookEndpoint
from integrations.services import (
    create_risk_assessment,
    get_current_risk_assessment,
    get_active_integration_client,
    payload_hash,
    register_idempotent_result,
    secret_safe_summary,
    _lock_risk_assessment_target,
    _risk_assessment_lock_id,
)


class IntegrationsSettingsTests(SimpleTestCase):
    def test_integrations_is_tenant_only(self):
        self.assertIn("integrations", settings.TENANT_APPS)
        self.assertNotIn("integrations", settings.SHARED_APPS)

    def test_risk_assessment_storage_does_not_add_rest_url_surface(self):
        url_patterns = " ".join(
            str(pattern.pattern).lower() for pattern in get_resolver().url_patterns
        )

        self.assertNotIn("risk-assessment", url_patterns)
        self.assertNotIn("risk_assessment", url_patterns)


class IntegrationSubstrateTests(TenantTestCase):
    @classmethod
    def setup_tenant(cls, tenant):
        tenant.name = "Tenant Alpha"

    def setUp(self):
        application_model = get_application_model()
        self.application = application_model.objects.create(
            name="ai-client",
            user=None,
            client_type=application_model.CLIENT_CONFIDENTIAL,
            authorization_grant_type=application_model.GRANT_CLIENT_CREDENTIALS,
        )
        self.integration_client = IntegrationClient.objects.create(
            name="AI Assistant",
            code="ai-assistant",
            integration_type=IntegrationClient.IntegrationType.AI_ASSISTANT,
            oauth_application=self.application,
            scope_codes=[
                IntegrationScope.AI_READ_REPORT,
                IntegrationScope.AI_CREATE_COMMENT,
            ],
        )

    def test_oauth_application_uses_nullable_service_identity(self):
        self.assertIsNone(self.application.user)
        self.assertEqual(self.application.CLIENT_CONFIDENTIAL, self.application.client_type)
        self.assertEqual(
            self.application.GRANT_CLIENT_CREDENTIALS,
            self.application.authorization_grant_type,
        )

    def test_active_client_with_required_scope_is_authorized(self):
        context = get_active_integration_client(
            self.application, required_scope=IntegrationScope.AI_CREATE_COMMENT
        )

        self.assertEqual(self.integration_client, context.integration_client)

    def test_missing_scope_is_denied_without_human_role_fallback(self):
        with self.assertRaises(IntegrationScopeDenied):
            get_active_integration_client(
                self.application, required_scope=IntegrationScope.RISK_UPDATE
            )

    def test_disabled_client_is_denied(self):
        self.integration_client.status = IntegrationClient.Status.DISABLED
        self.integration_client.save(update_fields=("status", "updated_at"))

        with self.assertRaises(IntegrationClientDenied):
            get_active_integration_client(
                self.application, required_scope=IntegrationScope.AI_READ_REPORT
            )

    def test_public_schema_fallback_is_denied_before_client_lookup(self):
        tenant_schema = connection.schema_name
        self.assertNotEqual("public", tenant_schema)

        with schema_context("public"):
            with self.assertRaises(PublicSchemaDenied):
                get_active_integration_client(
                    self.application, required_scope=IntegrationScope.AI_READ_REPORT
                )

    def test_client_requires_confidential_client_credentials_application(self):
        application_model = get_application_model()
        bad_application = application_model.objects.create(
            name="bad-client",
            user=None,
            client_type=application_model.CLIENT_PUBLIC,
            authorization_grant_type=application_model.GRANT_PASSWORD,
        )
        client = IntegrationClient(
            name="Bad Client",
            code="bad-client",
            oauth_application=bad_application,
            scope_codes=[IntegrationScope.AI_READ_REPORT],
        )

        with self.assertRaises(ValidationError):
            client.full_clean()

    def test_service_denies_saved_client_with_bad_oauth_application_shape(self):
        application_model = get_application_model()
        bad_application = application_model.objects.create(
            name="saved-bad-client",
            user=None,
            client_type=application_model.CLIENT_PUBLIC,
            authorization_grant_type=application_model.GRANT_PASSWORD,
        )
        IntegrationClient.objects.create(
            name="Saved Bad Client",
            code="saved-bad-client",
            oauth_application=bad_application,
            scope_codes=[IntegrationScope.AI_READ_REPORT],
        )

        with self.assertRaises(IntegrationClientDenied):
            get_active_integration_client(
                bad_application, required_scope=IntegrationScope.AI_READ_REPORT
            )

    def test_idempotency_replays_same_payload_for_same_action(self):
        first = register_idempotent_result(
            integration_client=self.integration_client,
            action_type="ai.create_comment",
            key="idem-1",
            request_payload={"body": "same"},
            response_status_code=202,
            response_summary={"commentId": "1"},
        )
        second = register_idempotent_result(
            integration_client=self.integration_client,
            action_type="ai.create_comment",
            key="idem-1",
            request_payload={"body": "same"},
            response_status_code=202,
            response_summary={"commentId": "1"},
        )

        self.assertFalse(first.replayed)
        self.assertTrue(second.replayed)
        self.assertEqual(first.record.id, second.record.id)
        self.assertEqual(
            "(integration_client, action_type, key)",
            second.record.uniqueness_boundary,
        )

    def test_idempotency_same_key_can_be_used_for_different_action_type(self):
        first = register_idempotent_result(
            integration_client=self.integration_client,
            action_type="ai.create_comment",
            key="idem-2",
            request_payload={"body": "comment"},
        )
        second = register_idempotent_result(
            integration_client=self.integration_client,
            action_type="risk.update",
            key="idem-2",
            request_payload={"level": "HIGH"},
        )

        self.assertNotEqual(first.record.id, second.record.id)

    def test_idempotency_rejects_same_action_key_with_different_payload(self):
        register_idempotent_result(
            integration_client=self.integration_client,
            action_type="ai.create_comment",
            key="idem-3",
            request_payload={"body": "original"},
        )

        with self.assertRaises(IntegrationIdempotencyConflict):
            register_idempotent_result(
                integration_client=self.integration_client,
                action_type="ai.create_comment",
                key="idem-3",
                request_payload={"body": "changed"},
            )

    def test_payload_hash_is_canonical_and_summary_redacts_secret_material(self):
        first_hash = payload_hash({"b": 2, "a": 1})
        second_hash = payload_hash({"a": 1, "b": 2})

        self.assertEqual(first_hash, second_hash)
        self.assertEqual(
            {
                "Authorization": "[REDACTED]",
                "metadata": {"clientSecret": "[REDACTED]", "note": "ok"},
            },
            secret_safe_summary(
                {
                    "Authorization": "Bearer secret",
                    "metadata": {"clientSecret": "plain", "note": "ok"},
                }
            ),
        )

    def test_secret_safe_summary_redacts_api_keys_and_header_arrays(self):
        self.assertEqual(
            {
                "X-Api-Key": "[REDACTED]",
                "metadata": {"apiKey": "[REDACTED]", "authorityId": 10},
                "headers": [
                    {"name": "X-Api-Key", "value": "[REDACTED]"},
                    {"name": "X-Correlation-ID", "value": "trace-1"},
                ],
            },
            secret_safe_summary(
                {
                    "X-Api-Key": "plain",
                    "metadata": {"apiKey": "plain", "authorityId": 10},
                    "headers": [
                        {"name": "X-Api-Key", "value": "plain"},
                        {"name": "X-Correlation-ID", "value": "trace-1"},
                    ],
                }
            ),
        )

        self.assertEqual(
            {"clientKey": "[REDACTED]"},
            secret_safe_summary({"clientKey": "plain"}),
        )
        self.assertEqual(
            {
                "headers": [
                    {"name": "X-Client-Key", "value": "[REDACTED]"},
                ]
            },
            secret_safe_summary(
                {"headers": [{"name": "X-Client-Key", "value": "plain"}]}
            ),
        )
        self.assertEqual(
            {"authorityId": 10},
            secret_safe_summary({"authorityId": 10}),
        )

    def test_webhook_endpoint_rejects_secret_bearing_custom_headers(self):
        secret_header_sets = [
            {"Authorization": "Bearer plain"},
            {"X-Api-Key": "plain"},
            {"X-Client-Key": "plain"},
            {"Api-Key": "plain"},
            {"apiKey": "plain"},
            {"X-Auth-Token": "plain"},
            {"Token": "plain"},
            {"Secret": "plain"},
            {"Signature": "plain"},
            {"Password": "plain"},
            [{"name": "X-Api-Key", "value": "plain"}],
            [{"Name": "X-Api-Key", "Value": "plain"}],
        ]

        for custom_headers in secret_header_sets:
            with self.subTest(custom_headers=custom_headers):
                endpoint = WebhookEndpoint(
                    integration_client=self.integration_client,
                    name="secret-header",
                    url="https://external.example.test/webhook",
                    event_types=["report.submitted"],
                    custom_headers=custom_headers,
                )

                with self.assertRaises(ValidationError):
                    endpoint.full_clean()

        with self.assertRaises(ValidationError):
            WebhookEndpoint.objects.create(
                integration_client=self.integration_client,
                name="direct-save-secret-header",
                url="https://external.example.test/webhook",
                event_types=["report.submitted"],
                custom_headers={"X-Api-Key": "plain"},
            )

    def test_webhook_endpoint_allows_non_secret_custom_headers(self):
        endpoint = WebhookEndpoint(
            integration_client=self.integration_client,
            name="non-secret-header",
            url="https://external.example.test/webhook",
            event_types=["report.submitted"],
            custom_headers={
                "authorityId": 10,
                "X-Correlation-ID": "trace-1",
                "X-OHTK-Source": "integration",
                "headers": [{"name": "X-Request-ID", "value": "req-1"}],
            },
        )

        endpoint.full_clean()

    def test_webhook_endpoint_stores_secret_references_not_plaintext_secrets(self):
        endpoint = WebhookEndpoint.objects.create(
            integration_client=self.integration_client,
            name="report-submitted",
            url="https://external.example.test/webhook",
            event_types=["report.submitted"],
            active_signing_secret_ref="secret-manager://tenant/ai/active",
            active_signing_secret_version=1,
            next_signing_secret_ref="secret-manager://tenant/ai/next",
            next_signing_secret_version=2,
        )

        self.assertEqual(
            "secret-manager://tenant/ai/active",
            endpoint.active_signing_secret_ref,
        )
        self.assertFalse(hasattr(endpoint, "signing_secret"))


class RiskAssessmentStorageTests(TenantTestCase):
    @classmethod
    def setup_tenant(cls, tenant):
        tenant.name = "Tenant Alpha"

    def setUp(self):
        application_model = get_application_model()
        self.risk_application = application_model.objects.create(
            name="risk-client",
            user=None,
            client_type=application_model.CLIENT_CONFIDENTIAL,
            authorization_grant_type=application_model.GRANT_CLIENT_CREDENTIALS,
        )
        self.risk_client = IntegrationClient.objects.create(
            name="Risk Evaluator",
            code="risk-evaluator",
            integration_type=IntegrationClient.IntegrationType.RISK_EVALUATOR,
            oauth_application=self.risk_application,
            scope_codes=[IntegrationScope.RISK_UPDATE],
        )
        self.ai_application = application_model.objects.create(
            name="ai-client",
            user=None,
            client_type=application_model.CLIENT_CONFIDENTIAL,
            authorization_grant_type=application_model.GRANT_CLIENT_CREDENTIALS,
        )
        self.ai_client = IntegrationClient.objects.create(
            name="AI Assistant",
            code="ai-assistant-risk",
            integration_type=IntegrationClient.IntegrationType.AI_ASSISTANT,
            oauth_application=self.ai_application,
            scope_codes=[IntegrationScope.AI_READ_REPORT],
        )

    def test_current_assessment_replacement_preserves_history(self):
        first = create_risk_assessment(
            target_type=RiskAssessment.TargetType.REPORT,
            target_id="report-1",
            level=RiskAssessment.Level.HIGH,
            score="0.8400",
            factors=[{"key": "mortality_count", "weight": 0.5}],
            source=RiskAssessment.Source.EXTERNAL_RISK_EVALUATOR,
            evaluator_version="risk-v1",
            integration_client=self.risk_client,
            external_assessment_id="risk-001",
        )
        second = create_risk_assessment(
            target_type=RiskAssessment.TargetType.REPORT,
            target_id="report-1",
            level=RiskAssessment.Level.LOW,
            score="0.1000",
            factors=[{"key": "officer_override"}],
            source=RiskAssessment.Source.HUMAN,
        )

        first.assessment.refresh_from_db()
        self.assertFalse(first.assessment.is_current)
        self.assertTrue(second.assessment.is_current)
        self.assertEqual(1, second.replaced_current_count)
        self.assertEqual(
            second.assessment,
            get_current_risk_assessment(
                target_type=RiskAssessment.TargetType.REPORT,
                target_id="report-1",
            ),
        )
        self.assertEqual(
            [second.assessment.id, first.assessment.id],
            list(
                RiskAssessment.objects.filter(
                    target_type=RiskAssessment.TargetType.REPORT,
                    target_id="report-1",
                ).values_list("id", flat=True)
            ),
        )

    def test_current_assessment_takes_per_target_advisory_lock(self):
        with mock.patch(
            "integrations.services._lock_risk_assessment_target"
        ) as lock_target:
            create_risk_assessment(
                target_type=RiskAssessment.TargetType.REPORT,
                target_id="report-lock",
                level=RiskAssessment.Level.HIGH,
                source=RiskAssessment.Source.RULE_ENGINE,
            )

        lock_target.assert_called_once_with(
            RiskAssessment.TargetType.REPORT,
            "report-lock",
        )

    def test_non_current_assessment_does_not_take_current_projection_lock(self):
        with mock.patch(
            "integrations.services._lock_risk_assessment_target"
        ) as lock_target:
            create_risk_assessment(
                target_type=RiskAssessment.TargetType.REPORT,
                target_id="report-historical",
                level=RiskAssessment.Level.HIGH,
                source=RiskAssessment.Source.RULE_ENGINE,
                is_current=False,
            )

        lock_target.assert_not_called()

    def test_risk_assessment_target_lock_uses_stable_postgres_advisory_lock(self):
        expected_lock_id = _risk_assessment_lock_id(
            RiskAssessment.TargetType.REPORT,
            "report-lock",
        )

        with mock.patch("integrations.services.connection.cursor") as cursor_factory:
            cursor = cursor_factory.return_value.__enter__.return_value

            _lock_risk_assessment_target(
                RiskAssessment.TargetType.REPORT,
                "report-lock",
            )

        cursor.execute.assert_called_once_with(
            "SELECT pg_advisory_xact_lock(%s)",
            [expected_lock_id],
        )
        self.assertNotEqual(
            expected_lock_id,
            _risk_assessment_lock_id(
                RiskAssessment.TargetType.CASE,
                "report-lock",
            ),
        )

    def test_non_current_assessment_does_not_replace_current_projection(self):
        current = create_risk_assessment(
            target_type=RiskAssessment.TargetType.CASE,
            target_id="case-1",
            level=RiskAssessment.Level.MEDIUM,
            source=RiskAssessment.Source.RULE_ENGINE,
        )
        historical = create_risk_assessment(
            target_type=RiskAssessment.TargetType.CASE,
            target_id="case-1",
            level=RiskAssessment.Level.HIGH,
            source=RiskAssessment.Source.RULE_ENGINE,
            is_current=False,
        )

        current.assessment.refresh_from_db()
        self.assertTrue(current.assessment.is_current)
        self.assertFalse(historical.assessment.is_current)
        self.assertEqual(0, historical.replaced_current_count)
        self.assertEqual(
            current.assessment,
            get_current_risk_assessment(
                target_type=RiskAssessment.TargetType.CASE,
                target_id="case-1",
            ),
        )

    def test_current_projection_is_separated_by_target_type_and_id(self):
        report_assessment = create_risk_assessment(
            target_type=RiskAssessment.TargetType.REPORT,
            target_id="shared-id",
            level=RiskAssessment.Level.LOW,
            source=RiskAssessment.Source.RULE_ENGINE,
        )
        case_assessment = create_risk_assessment(
            target_type=RiskAssessment.TargetType.CASE,
            target_id="shared-id",
            level=RiskAssessment.Level.HIGH,
            source=RiskAssessment.Source.RULE_ENGINE,
        )
        cluster_assessment = create_risk_assessment(
            target_type=RiskAssessment.TargetType.CLUSTER,
            target_id="cluster-1",
            level=RiskAssessment.Level.CRITICAL,
            source=RiskAssessment.Source.RULE_ENGINE,
        )

        self.assertTrue(report_assessment.assessment.is_current)
        self.assertTrue(case_assessment.assessment.is_current)
        self.assertTrue(cluster_assessment.assessment.is_current)
        self.assertEqual(3, RiskAssessment.objects.filter(is_current=True).count())

    def test_optional_integration_client_for_human_and_rule_engine_sources(self):
        human = create_risk_assessment(
            target_type=RiskAssessment.TargetType.REPORT,
            target_id="human-report",
            level=RiskAssessment.Level.MEDIUM,
            source=RiskAssessment.Source.HUMAN,
        )
        rule_engine = create_risk_assessment(
            target_type=RiskAssessment.TargetType.REPORT,
            target_id="rule-report",
            level=RiskAssessment.Level.HIGH,
            source=RiskAssessment.Source.RULE_ENGINE,
        )

        self.assertIsNone(human.assessment.integration_client)
        self.assertIsNone(rule_engine.assessment.integration_client)

    def test_external_source_requires_active_risk_update_integration_client(self):
        with self.assertRaises(ValidationError):
            create_risk_assessment(
                target_type=RiskAssessment.TargetType.REPORT,
                target_id="report-2",
                level=RiskAssessment.Level.HIGH,
                source=RiskAssessment.Source.EXTERNAL_RISK_EVALUATOR,
            )

        with self.assertRaises(ValidationError):
            create_risk_assessment(
                target_type=RiskAssessment.TargetType.REPORT,
                target_id="report-2",
                level=RiskAssessment.Level.HIGH,
                source=RiskAssessment.Source.HUMAN,
                integration_client=self.risk_client,
            )

        with self.assertRaises(ValidationError):
            create_risk_assessment(
                target_type=RiskAssessment.TargetType.REPORT,
                target_id="report-2",
                level=RiskAssessment.Level.HIGH,
                source=RiskAssessment.Source.AI,
                integration_client=self.ai_client,
            )

    def test_invalid_target_level_source_and_score_are_rejected(self):
        invalid_payloads = [
            {
                "target_type": "incident",
                "target_id": "report-3",
                "level": RiskAssessment.Level.HIGH,
                "source": RiskAssessment.Source.RULE_ENGINE,
            },
            {
                "target_type": RiskAssessment.TargetType.REPORT,
                "target_id": "report-3",
                "level": "SEVERE",
                "source": RiskAssessment.Source.RULE_ENGINE,
            },
            {
                "target_type": RiskAssessment.TargetType.REPORT,
                "target_id": "report-3",
                "level": RiskAssessment.Level.HIGH,
                "source": "bot",
            },
            {
                "target_type": RiskAssessment.TargetType.REPORT,
                "target_id": "report-3",
                "level": RiskAssessment.Level.HIGH,
                "source": RiskAssessment.Source.RULE_ENGINE,
                "score": "1.1000",
            },
        ]

        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                with self.assertRaises(ValidationError):
                    create_risk_assessment(**payload)

    def test_factors_are_stored_as_secret_safe_summary(self):
        result = create_risk_assessment(
            target_type=RiskAssessment.TargetType.REPORT,
            target_id="report-secret",
            level=RiskAssessment.Level.HIGH,
            source=RiskAssessment.Source.EXTERNAL_RISK_EVALUATOR,
            integration_client=self.risk_client,
            factors=[
                {"key": "mortality_count", "weight": 0.5},
                {"name": "X-Api-Key", "value": "plain"},
            ],
        )

        self.assertEqual(
            [
                {"key": "mortality_count", "weight": 0.5},
                {"name": "X-Api-Key", "value": "[REDACTED]"},
            ],
            result.assessment.factors,
        )
