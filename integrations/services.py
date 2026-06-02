import hashlib
from dataclasses import dataclass

from django import VERSION as DJANGO_VERSION
from django.db import IntegrityError, transaction
from django.db import connection
from django.utils import timezone
from django_tenants.utils import get_public_schema_name

from integrations.exceptions import (
    IntegrationClientDenied,
    IntegrationIdempotencyConflict,
    IntegrationScopeDenied,
    PublicSchemaDenied,
)
from integrations.models import (
    IntegrationClient,
    IntegrationIdempotencyRecord,
    IntegrationReportComment,
    RiskAssessment,
)
from integrations.utils import payload_hash, secret_safe_summary


@dataclass(frozen=True)
class IntegrationAuthContext:
    integration_client: IntegrationClient


@dataclass(frozen=True)
class IdempotencyResult:
    record: IntegrationIdempotencyRecord
    replayed: bool


@dataclass(frozen=True)
class RiskAssessmentResult:
    assessment: RiskAssessment
    replaced_current_count: int


def assert_integration_tenant_schema():
    schema_name = getattr(connection, "schema_name", None)
    if schema_name == get_public_schema_name():
        raise PublicSchemaDenied("Integration access is not allowed on the public schema.")
    if not schema_name:
        raise PublicSchemaDenied("Integration access requires a selected tenant schema.")


def get_active_integration_client(oauth_application, required_scope=None):
    assert_integration_tenant_schema()

    if oauth_application is None:
        raise IntegrationClientDenied("Integration OAuth application is required.")

    if oauth_application.client_type != oauth_application.CLIENT_CONFIDENTIAL:
        raise IntegrationClientDenied(
            "Integration OAuth application must be confidential."
        )
    if (
        oauth_application.authorization_grant_type
        != oauth_application.GRANT_CLIENT_CREDENTIALS
    ):
        raise IntegrationClientDenied(
            "Integration OAuth application must use client credentials."
        )

    try:
        integration_client = IntegrationClient.objects.get(
            oauth_application=oauth_application
        )
    except IntegrationClient.DoesNotExist as exc:
        raise IntegrationClientDenied(
            "OAuth application is not linked to an integration client."
        ) from exc

    if not integration_client.is_active:
        raise IntegrationClientDenied("Integration client is not active.")

    if required_scope and not integration_client.has_scope(required_scope):
        raise IntegrationScopeDenied(
            f"Integration client lacks required scope: {required_scope}"
        )

    return IntegrationAuthContext(integration_client=integration_client)


def register_idempotent_result(
    *,
    integration_client,
    action_type,
    key,
    request_payload,
    response_status_code=None,
    response_summary=None,
    target_type="",
    target_id="",
    action_log=None,
    expires_at=None,
):
    if not key:
        raise ValueError("Integration idempotency key is required.")

    request_payload_hash = payload_hash(request_payload)

    try:
        with transaction.atomic():
            record, created = IntegrationIdempotencyRecord.objects.get_or_create(
                integration_client=integration_client,
                action_type=action_type,
                key=key,
                defaults={
                    "target_type": target_type,
                    "target_id": target_id,
                    "request_payload_hash": request_payload_hash,
                    "response_status_code": response_status_code,
                    "response_summary": response_summary or {},
                    "action_log": action_log,
                    "expires_at": expires_at,
                },
            )
    except IntegrityError:
        record = IntegrationIdempotencyRecord.objects.get(
            integration_client=integration_client,
            action_type=action_type,
            key=key,
        )
        created = False

    if record.request_payload_hash != request_payload_hash:
        raise IntegrationIdempotencyConflict(
            "Idempotency key was reused with a different request payload."
        )

    return IdempotencyResult(record=record, replayed=not created)


def claim_idempotency_key(
    *,
    integration_client,
    action_type,
    key,
    request_payload,
    target_type="",
    target_id="",
    expires_at=None,
):
    if not key:
        raise ValueError("Integration idempotency key is required.")

    target_type_value = "" if target_type is None else str(target_type)
    target_id_value = "" if target_id is None else str(target_id)
    request_payload_hash = payload_hash(request_payload)

    try:
        with transaction.atomic():
            record, created = IntegrationIdempotencyRecord.objects.get_or_create(
                integration_client=integration_client,
                action_type=action_type,
                key=key,
                defaults={
                    "target_type": target_type_value,
                    "target_id": target_id_value,
                    "request_payload_hash": request_payload_hash,
                    "expires_at": expires_at,
                },
            )
    except IntegrityError:
        record = IntegrationIdempotencyRecord.objects.get(
            integration_client=integration_client,
            action_type=action_type,
            key=key,
        )
        created = False

    if record.target_type != target_type_value or record.target_id != target_id_value:
        raise IntegrationIdempotencyConflict(
            "Idempotency key was reused with a different target."
        )

    if record.request_payload_hash != request_payload_hash:
        raise IntegrationIdempotencyConflict(
            "Idempotency key was reused with a different request payload."
        )

    return IdempotencyResult(record=record, replayed=not created)


def create_integration_report_comment(
    *,
    report,
    integration_client,
    body,
    visibility=IntegrationReportComment.Visibility.STAFF,
    external_action_id="",
    metadata=None,
    recommendation=None,
):
    comment = IntegrationReportComment(
        report=report,
        integration_client=integration_client,
        body=body,
        visibility=visibility,
        external_action_id=external_action_id,
        metadata=metadata or {},
        recommendation=recommendation or {},
    )
    comment.save()
    return comment


def create_risk_assessment(
    *,
    target_type,
    target_id,
    level,
    source,
    score=None,
    factors=None,
    evaluator_version="",
    integration_client=None,
    external_assessment_id="",
    is_current=True,
):
    target_id_value = "" if target_id is None else str(target_id)

    assessment = RiskAssessment(
        target_type=target_type,
        target_id=target_id_value,
        level=level,
        score=score,
        factors=factors if factors is not None else [],
        source=source,
        evaluator_version=evaluator_version,
        integration_client=integration_client,
        external_assessment_id=external_assessment_id,
        is_current=is_current,
    )
    if DJANGO_VERSION >= (4, 1):
        assessment.full_clean(validate_constraints=False)
    else:
        assessment.full_clean()

    replaced_current_count = 0
    with transaction.atomic():
        if assessment.is_current:
            _lock_risk_assessment_target(
                assessment.target_type,
                assessment.target_id,
            )
            current_rows = RiskAssessment.objects.select_for_update().filter(
                target_type=assessment.target_type,
                target_id=assessment.target_id,
                is_current=True,
            )
            replaced_current_count = current_rows.update(
                is_current=False,
                updated_at=timezone.now(),
            )

        assessment.save()

    return RiskAssessmentResult(
        assessment=assessment,
        replaced_current_count=replaced_current_count,
    )


def get_current_risk_assessment(*, target_type, target_id):
    return (
        RiskAssessment.objects.filter(
            target_type=target_type,
            target_id=str(target_id),
            is_current=True,
        )
        .order_by("-created_at")
        .first()
    )


def _lock_risk_assessment_target(target_type, target_id):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT pg_advisory_xact_lock(%s)",
            [_risk_assessment_lock_id(target_type, target_id)],
        )


def _risk_assessment_lock_id(target_type, target_id):
    lock_key = f"integrations.risk_assessment:{target_type}:{target_id}"
    digest = hashlib.sha256(lock_key.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=True)
