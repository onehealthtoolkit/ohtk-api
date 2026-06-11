import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from common.models import BaseModel, BaseModelManager
from integrations.constants import (
    IDEMPOTENCY_UNIQUENESS,
    IntegrationEventType,
    IntegrationScope,
    is_secret_key_name,
)
from integrations.utils import secret_safe_summary


class IntegrationClient(BaseModel):
    class IntegrationType(models.TextChoices):
        AI_ASSISTANT = "AI_ASSISTANT", "AI assistant"
        CLUSTER_DETECTOR = "CLUSTER_DETECTOR", "Cluster detector"
        RISK_EVALUATOR = "RISK_EVALUATOR", "Risk evaluator"
        GENERIC = "GENERIC", "Generic"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        DISABLED = "DISABLED", "Disabled"
        REVOKED = "REVOKED", "Revoked"

    class Meta:
        ordering = ("code",)
        constraints = [
            models.UniqueConstraint(
                fields=["code"],
                condition=Q(deleted_at__isnull=True),
                name="unique_active_integration_client_code",
            )
        ]

    objects = BaseModelManager()

    name = models.CharField(max_length=200)
    code = models.SlugField(max_length=80)
    integration_type = models.CharField(
        choices=IntegrationType.choices,
        max_length=40,
        default=IntegrationType.GENERIC,
    )
    oauth_application = models.OneToOneField(
        "oauth2_provider.Application",
        on_delete=models.PROTECT,
        related_name="integration_client",
    )
    status = models.CharField(
        choices=Status.choices,
        max_length=20,
        default=Status.ACTIVE,
    )
    scope_codes = models.JSONField(default=list, blank=True)
    allowed_callback_domains = models.JSONField(default=list, blank=True)
    rate_limit_policy = models.JSONField(default=dict, blank=True)

    @property
    def is_active(self):
        return self.status == self.Status.ACTIVE and self.deleted_at is None

    def has_scope(self, scope_code):
        return scope_code in (self.scope_codes or [])

    def clean(self):
        super().clean()
        invalid_scopes = set(self.scope_codes or []) - IntegrationScope.CODES
        if invalid_scopes:
            raise ValidationError(
                {"scope_codes": f"Unknown integration scopes: {sorted(invalid_scopes)}"}
            )

        application = self.oauth_application
        if application.client_type != application.CLIENT_CONFIDENTIAL:
            raise ValidationError(
                {"oauth_application": "Integration OAuth applications must be confidential."}
            )
        if (
            application.authorization_grant_type
            != application.GRANT_CLIENT_CREDENTIALS
        ):
            raise ValidationError(
                {
                    "oauth_application": (
                        "Integration OAuth applications must use client credentials."
                    )
                }
            )

    def __str__(self):
        return f"{self.code} ({self.integration_type})"


class WebhookEndpoint(BaseModel):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        DISABLED = "DISABLED", "Disabled"

    class Meta:
        ordering = ("integration_client__code", "name")
        constraints = [
            models.UniqueConstraint(
                fields=["integration_client", "name"],
                condition=Q(deleted_at__isnull=True),
                name="unique_active_webhook_endpoint_name",
            )
        ]

    objects = BaseModelManager()

    integration_client = models.ForeignKey(
        IntegrationClient, on_delete=models.CASCADE, related_name="webhook_endpoints"
    )
    name = models.CharField(max_length=200)
    url = models.URLField(max_length=1000)
    event_types = models.JSONField(default=list, blank=True)
    status = models.CharField(
        choices=Status.choices,
        max_length=20,
        default=Status.ACTIVE,
    )
    schema_version = models.CharField(max_length=40, default="2026-06-02")
    active_signing_secret_ref = models.CharField(max_length=300, blank=True)
    active_signing_secret_version = models.PositiveIntegerField(default=1)
    next_signing_secret_ref = models.CharField(max_length=300, blank=True)
    next_signing_secret_version = models.PositiveIntegerField(null=True, blank=True)
    timeout_seconds = models.PositiveIntegerField(default=10)
    max_attempts = models.PositiveIntegerField(default=5)
    retry_policy = models.JSONField(default=dict, blank=True)
    custom_headers = models.JSONField(default=dict, blank=True)
    last_rotated_at = models.DateTimeField(null=True, blank=True)

    def clean(self):
        super().clean()
        invalid_event_types = set(self.event_types or []) - IntegrationEventType.CODES
        if invalid_event_types:
            raise ValidationError(
                {"event_types": f"Unknown event types: {sorted(invalid_event_types)}"}
            )

        secret_headers = sorted(_find_secret_header_names(self.custom_headers))
        if secret_headers:
            raise ValidationError(
                {
                    "custom_headers": (
                        "Custom headers must be non-secret only. "
                        f"Use secret references for: {secret_headers}"
                    )
                }
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.integration_client.code} {self.name}"


class IntegrationEvent(BaseModel):
    class Status(models.TextChoices):
        RECORDED = "RECORDED", "Recorded"
        QUEUED = "QUEUED", "Queued"
        CANCELLED = "CANCELLED", "Cancelled"

    class Meta:
        ordering = ("-produced_at", "-created_at")
        constraints = [
            models.UniqueConstraint(
                fields=["event_type", "source_app", "subject_type", "subject_id"],
                condition=Q(
                    deleted_at__isnull=True,
                    event_type=IntegrationEventType.REPORT_SUBMITTED,
                    source_app="reports",
                    subject_type="reports.IncidentReport",
                ),
                name="unique_active_report_submitted_event_subject",
            )
        ]

    objects = BaseModelManager()

    event_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    event_type = models.CharField(
        choices=IntegrationEventType.CHOICES,
        max_length=80,
        default=IntegrationEventType.REPORT_SUBMITTED,
    )
    schema_version = models.CharField(max_length=40, default="2026-06-02")
    source_app = models.CharField(max_length=80)
    subject_type = models.CharField(max_length=80)
    subject_id = models.CharField(max_length=120)
    payload_hash = models.CharField(max_length=64)
    payload_summary = models.JSONField(default=dict, blank=True)
    produced_at = models.DateTimeField()
    status = models.CharField(
        choices=Status.choices,
        max_length=20,
        default=Status.RECORDED,
    )

    def __str__(self):
        return f"{self.event_type} {self.event_id}"


class WebhookDelivery(BaseModel):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        DELIVERING = "DELIVERING", "Delivering"
        SUCCEEDED = "SUCCEEDED", "Succeeded"
        FAILED = "FAILED", "Failed"
        CANCELLED = "CANCELLED", "Cancelled"

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=["event", "endpoint"],
                condition=Q(deleted_at__isnull=True),
                name="unique_active_webhook_delivery_event_endpoint",
            )
        ]

    objects = BaseModelManager()

    event = models.ForeignKey(
        IntegrationEvent, on_delete=models.CASCADE, related_name="deliveries"
    )
    endpoint = models.ForeignKey(
        WebhookEndpoint, on_delete=models.CASCADE, related_name="deliveries"
    )
    delivery_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    status = models.CharField(
        choices=Status.choices,
        max_length=20,
        default=Status.PENDING,
    )
    attempt_count = models.PositiveIntegerField(default=0)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    next_retry_at = models.DateTimeField(null=True, blank=True)
    response_status_code = models.PositiveIntegerField(null=True, blank=True)
    response_body_summary = models.JSONField(default=dict, blank=True)
    failure_reason = models.CharField(max_length=500, blank=True)
    payload_hash = models.CharField(max_length=64)
    signing_secret_version = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.endpoint} {self.status}"


class IntegrationActionLog(BaseModel):
    class ResultStatus(models.TextChoices):
        ACCEPTED = "ACCEPTED", "Accepted"
        REPLAYED = "REPLAYED", "Replayed"
        REJECTED = "REJECTED", "Rejected"
        FAILED = "FAILED", "Failed"

    class Meta:
        ordering = ("-created_at",)

    objects = BaseModelManager()

    action_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    integration_client = models.ForeignKey(
        IntegrationClient, on_delete=models.PROTECT, related_name="action_logs"
    )
    action_type = models.CharField(max_length=100)
    required_scope = models.CharField(max_length=80)
    target_type = models.CharField(max_length=80, blank=True)
    target_id = models.CharField(max_length=120, blank=True)
    idempotency_key = models.CharField(max_length=200, blank=True)
    external_action_id = models.CharField(max_length=200, blank=True)
    payload_hash = models.CharField(max_length=64, blank=True)
    request_headers_summary = models.JSONField(default=dict, blank=True)
    result_status = models.CharField(
        choices=ResultStatus.choices,
        max_length=20,
        default=ResultStatus.ACCEPTED,
    )
    result_summary = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"{self.integration_client.code} {self.action_type} {self.result_status}"


class IntegrationIdempotencyRecord(BaseModel):
    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=["integration_client", "action_type", "key"],
                condition=Q(deleted_at__isnull=True),
                name="unique_active_integration_idempotency_action_key",
            )
        ]
        verbose_name_plural = "integration idempotency records"

    objects = BaseModelManager()

    integration_client = models.ForeignKey(
        IntegrationClient,
        on_delete=models.CASCADE,
        related_name="idempotency_records",
    )
    key = models.CharField(max_length=200)
    action_type = models.CharField(max_length=100)
    target_type = models.CharField(max_length=80, blank=True)
    target_id = models.CharField(max_length=120, blank=True)
    request_payload_hash = models.CharField(max_length=64)
    response_status_code = models.PositiveIntegerField(null=True, blank=True)
    response_summary = models.JSONField(default=dict, blank=True)
    action_log = models.OneToOneField(
        IntegrationActionLog,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="idempotency_record",
    )
    expires_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.integration_client.code} {self.action_type} {self.key}"

    @property
    def uniqueness_boundary(self):
        return IDEMPOTENCY_UNIQUENESS


class RiskAssessment(BaseModel):
    class TargetType(models.TextChoices):
        REPORT = "report", "Report"
        CASE = "case", "Case"
        CLUSTER = "cluster", "Cluster"

    class Level(models.TextChoices):
        LOW = "LOW", "Low"
        MEDIUM = "MEDIUM", "Medium"
        HIGH = "HIGH", "High"
        CRITICAL = "CRITICAL", "Critical"

    class Source(models.TextChoices):
        RULE_ENGINE = "rule_engine", "Rule engine"
        EXTERNAL_RISK_EVALUATOR = (
            "external_risk_evaluator",
            "External risk evaluator",
        )
        AI = "ai", "AI"
        HUMAN = "human", "Human"

    INTEGRATION_SOURCES = {
        Source.EXTERNAL_RISK_EVALUATOR,
        Source.AI,
    }

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(
                fields=["target_type", "target_id", "-created_at"],
                name="risk_assessment_target_idx",
            ),
            models.Index(
                fields=["target_type", "target_id", "is_current"],
                name="risk_assessment_current_idx",
            ),
            models.Index(
                fields=["integration_client", "external_assessment_id"],
                name="risk_assessment_external_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["target_type", "target_id"],
                condition=Q(is_current=True, deleted_at__isnull=True),
                name="unique_current_risk_assessment_target",
            )
        ]

    objects = BaseModelManager()

    target_type = models.CharField(choices=TargetType.choices, max_length=20)
    target_id = models.CharField(max_length=120)
    level = models.CharField(choices=Level.choices, max_length=20)
    score = models.DecimalField(
        max_digits=5, decimal_places=4, null=True, blank=True
    )
    factors = models.JSONField(default=list, blank=True)
    source = models.CharField(choices=Source.choices, max_length=40)
    evaluator_version = models.CharField(max_length=120, blank=True)
    integration_client = models.ForeignKey(
        IntegrationClient,
        on_delete=models.PROTECT,
        related_name="risk_assessments",
        null=True,
        blank=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="risk_assessments",
        null=True,
        blank=True,
    )
    external_assessment_id = models.CharField(max_length=200, blank=True)
    is_current = models.BooleanField(default=True)

    def clean(self):
        super().clean()
        errors = {}

        if not self.target_id:
            errors["target_id"] = "Risk assessment target_id is required."

        if self.score is not None:
            score = Decimal(self.score)
            if score < Decimal("0") or score > Decimal("1"):
                errors["score"] = "Risk assessment score must be between 0 and 1."

        source_requires_client = self.source in self.INTEGRATION_SOURCES
        if source_requires_client and self.integration_client is None:
            errors["integration_client"] = (
                "Integration-authored risk assessments require an integration client."
            )
        if not source_requires_client and self.integration_client is not None:
            errors["integration_client"] = (
                "Only integration-authored risk assessments may link an integration client."
            )

        if self.integration_client is not None:
            if not self.integration_client.is_active:
                errors["integration_client"] = (
                    "Risk assessment integration client must be active."
                )
            elif not self.integration_client.has_scope(IntegrationScope.RISK_UPDATE):
                errors["integration_client"] = (
                    "Risk assessment integration client requires risk:update scope."
                )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.factors = secret_safe_summary(
            self.factors, max_string_length=None, max_list_length=None
        )
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.target_type}:{self.target_id} {self.level}"


class IntegrationClusterResult(BaseModel):
    class Meta:
        ordering = ("-window_start", "-window_end", "-created_at")
        indexes = [
            models.Index(
                fields=["integration_client", "external_cluster_id"],
                name="int_cluster_external_idx",
            ),
            models.Index(
                fields=["cluster_id"],
                name="int_cluster_cluster_id_idx",
            ),
            models.Index(
                fields=["risk_level", "-window_start"],
                name="int_cluster_risk_window_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["integration_client", "external_cluster_id"],
                condition=Q(deleted_at__isnull=True),
                name="unique_active_integration_cluster_external",
            )
        ]

    objects = BaseModelManager()

    cluster_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    integration_client = models.ForeignKey(
        IntegrationClient,
        on_delete=models.PROTECT,
        related_name="cluster_results",
    )
    external_cluster_id = models.CharField(max_length=200)
    algorithm_version = models.CharField(max_length=120)
    window_start = models.DateField()
    window_end = models.DateField()
    incident_ids = models.JSONField(default=list, blank=True)
    authority_ids = models.JSONField(default=list, blank=True)
    village_ids = models.JSONField(default=list, blank=True)
    geometry = models.JSONField(null=True, blank=True)
    radius_meters = models.DecimalField(
        max_digits=12, decimal_places=3, null=True, blank=True
    )
    score = models.DecimalField(
        max_digits=5, decimal_places=4, null=True, blank=True
    )
    risk_level = models.CharField(
        choices=RiskAssessment.Level.choices,
        max_length=20,
        blank=True,
    )
    explanation = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    action_log = models.ForeignKey(
        IntegrationActionLog,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cluster_results",
    )

    def clean(self):
        super().clean()
        errors = {}

        if self.integration_client_id is None:
            errors["integration_client"] = (
                "Cluster results require an integration client."
            )
        elif not self.integration_client.is_active:
            errors["integration_client"] = (
                "Cluster result integration client must be active."
            )
        elif not self.integration_client.has_scope(IntegrationScope.CLUSTER_WRITE_RESULT):
            errors["integration_client"] = (
                "Cluster result integration client requires cluster:write_result scope."
            )

        if not self.external_cluster_id or not self.external_cluster_id.strip():
            errors["external_cluster_id"] = "external_cluster_id is required."

        if not self.algorithm_version or not self.algorithm_version.strip():
            errors["algorithm_version"] = "algorithm_version is required."

        if self.window_start and self.window_end and self.window_start > self.window_end:
            errors["window_end"] = "window_end must be on or after window_start."

        for field_name in ("incident_ids", "authority_ids", "village_ids"):
            if not isinstance(getattr(self, field_name), list):
                errors[field_name] = f"{field_name} must be a list."

        if self.geometry is not None and not isinstance(self.geometry, dict):
            errors["geometry"] = "geometry must be an object."

        if self.radius_meters is not None:
            radius_meters = Decimal(self.radius_meters)
            if radius_meters < Decimal("0"):
                errors["radius_meters"] = "radius_meters must be zero or greater."

        if self.score is not None:
            score = Decimal(self.score)
            if score < Decimal("0") or score > Decimal("1"):
                errors["score"] = "score must be between 0 and 1."

        if not isinstance(self.metadata, dict):
            errors["metadata"] = "metadata must be an object."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.metadata = secret_safe_summary(
            self.metadata, max_string_length=None, max_list_length=None
        )
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.integration_client.code} cluster:{self.external_cluster_id}"


class IntegrationReportComment(BaseModel):
    class Visibility(models.TextChoices):
        STAFF = "staff", "Staff"

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(
                fields=["report", "-created_at"],
                name="int_report_comment_report_idx",
            ),
            models.Index(
                fields=["integration_client", "external_action_id"],
                name="int_report_cmt_external_idx",
            ),
        ]

    objects = BaseModelManager()

    comment_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    report = models.ForeignKey(
        "reports.IncidentReport",
        on_delete=models.PROTECT,
        related_name="integration_comments",
    )
    integration_client = models.ForeignKey(
        IntegrationClient,
        on_delete=models.PROTECT,
        related_name="report_comments",
    )
    body = models.TextField()
    visibility = models.CharField(
        choices=Visibility.choices,
        max_length=20,
        default=Visibility.STAFF,
    )
    external_action_id = models.CharField(max_length=200, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    recommendation = models.JSONField(default=dict, blank=True)

    def clean(self):
        super().clean()
        errors = {}

        if not self.report_id:
            errors["report"] = "AI report comments require a report."

        if not self.body or not self.body.strip():
            errors["body"] = "AI report comments require a non-empty body."

        if self.integration_client_id is None:
            errors["integration_client"] = (
                "AI report comments require an integration client."
            )
        elif not self.integration_client.is_active:
            errors["integration_client"] = (
                "AI report comment integration client must be active."
            )
        elif not self.integration_client.has_scope(IntegrationScope.AI_CREATE_COMMENT):
            errors["integration_client"] = (
                "AI report comment integration client requires ai:create_comment scope."
            )

        if not isinstance(self.metadata, dict):
            errors["metadata"] = "AI report comment metadata must be an object."

        if not isinstance(self.recommendation, dict):
            errors["recommendation"] = (
                "AI report comment recommendation must be an object."
            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.metadata = secret_safe_summary(
            self.metadata, max_string_length=None, max_list_length=None
        )
        self.recommendation = secret_safe_summary(
            self.recommendation, max_string_length=None, max_list_length=None
        )
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.integration_client.code} report:{self.report_id}"


def _find_secret_header_names(headers):
    if isinstance(headers, dict):
        normalized_keys = {str(key).lower(): key for key in headers.keys()}
        secret_names = {
            str(key)
            for key in headers.keys()
            if str(key).lower() not in ("name", "value") and is_secret_key_name(key)
        }

        name_key = normalized_keys.get("name")
        name = headers.get(name_key) if name_key is not None else None
        if name and is_secret_key_name(name):
            secret_names.add(str(name))

        for value in headers.values():
            secret_names.update(_find_secret_header_names(value))

        return secret_names

    if isinstance(headers, list):
        secret_names = set()
        for item in headers:
            secret_names.update(_find_secret_header_names(item))
        return secret_names

    return set()
