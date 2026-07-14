import hashlib
import hmac
import json
import uuid
from dataclasses import dataclass
from datetime import timedelta
from urllib import request
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit

from django.db.models import Q
from django.db import transaction
from django.db import connection
from django.utils import timezone

from integrations.constants import IntegrationEventType, IntegrationScope
from integrations.exceptions import WebhookSigningSecretError
from integrations.models import (
    IntegrationClient,
    IntegrationEvent,
    WebhookDelivery,
    WebhookEndpoint,
)
from integrations.policy import IntegrationPolicyDenied, assert_integration_feature_enabled
from integrations.secret_resolvers import SettingsWebhookSigningSecretResolver
from integrations.services import assert_integration_tenant_schema
from integrations.utils import payload_hash, secret_safe_summary
from reports.models import IncidentReport


REPORT_SUBMITTED_SCHEMA_VERSION = "2026-06-02"


@dataclass(frozen=True)
class WebhookEventResult:
    event: IntegrationEvent
    deliveries: tuple


@dataclass(frozen=True)
class WebhookHttpResponse:
    status_code: int
    body: str


class UrlLibWebhookHttpClient:
    def send(self, *, url, headers, body, timeout):
        req = request.Request(
            url=url,
            data=body,
            headers=headers,
            method="POST",
        )
        with request.urlopen(req, timeout=timeout) as response:
            return WebhookHttpResponse(
                status_code=response.getcode(),
                body=response.read(4096).decode("utf-8", errors="replace"),
            )


def record_report_submitted_event(*, report_id, enqueue_delivery_tasks=True):
    assert_integration_tenant_schema()
    try:
        assert_integration_feature_enabled()
    except IntegrationPolicyDenied:
        return WebhookEventResult(event=None, deliveries=())

    report = (
        IncidentReport.objects.select_related("report_type", "report_type__category")
        .prefetch_related("relevant_authorities")
        .get(pk=report_id)
    )

    event = _get_or_create_report_submitted_event(report)

    _create_missing_deliveries(event)
    deliveries_to_enqueue = _deliveries_needing_enqueue(event)

    if deliveries_to_enqueue:
        event.status = IntegrationEvent.Status.QUEUED
        event.save(update_fields=("status", "updated_at"))

    if enqueue_delivery_tasks:
        from integrations.tasks import attempt_webhook_delivery

        for delivery in deliveries_to_enqueue:
            attempt_webhook_delivery.delay(delivery.id)

    return WebhookEventResult(event=event, deliveries=tuple(deliveries_to_enqueue))


def build_report_submitted_payload(*, report, event_id, produced_at):
    tenant = _tenant_payload()
    report_type = report.report_type

    return {
        "schemaVersion": REPORT_SUBMITTED_SCHEMA_VERSION,
        "eventType": IntegrationEventType.REPORT_SUBMITTED,
        "eventId": str(event_id),
        "producedAt": produced_at.isoformat(),
        "tenant": tenant,
        "report": {
            "id": str(report.id),
            "createdAt": _isoformat_or_none(report.created_at),
            "incidentDate": report.incident_date.isoformat()
            if report.incident_date
            else None,
            "reportType": {
                "id": str(report_type.id),
                "name": report_type.name,
                "category": str(report_type.category)
                if report_type.category_id
                else None,
            },
            "relevantAuthorityIds": list(
                report.relevant_authorities.order_by("id").values_list("id", flat=True)
            ),
            "caseId": str(report.case_id) if report.case_id else None,
        },
        "links": {
            "incident": f"/api/integrations/v1/incidents/{report.id}",
            "comments": f"/api/integrations/v1/reports/{report.id}/comments",
            "riskAssessments": (
                f"/api/integrations/v1/reports/{report.id}/risk-assessments"
            ),
        },
    }


def attempt_webhook_delivery_by_id(
    delivery_id,
    *,
    secret_resolver=None,
    http_client=None,
    timestamp=None,
):
    assert_integration_tenant_schema()

    now = timestamp or timezone.now()
    delivery = _claim_delivery_for_attempt(delivery_id, now)
    if delivery is None:
        return _load_delivery(delivery_id)

    if not _delivery_has_report_submitted_scope(delivery):
        return _mark_delivery_preflight_failed(
            delivery,
            failure_reason="Integration client lacks required scope: ai:read_report.",
        )

    if not endpoint_is_deliverable(delivery.endpoint):
        return _mark_delivery_preflight_failed(
            delivery,
            failure_reason="Webhook endpoint or integration client is not active.",
        )

    endpoint = delivery.endpoint
    integration_client = endpoint.integration_client

    resolver = secret_resolver or SettingsWebhookSigningSecretResolver()
    client = http_client or UrlLibWebhookHttpClient()
    body = _serialize_json_body(delivery.event.payload_summary)
    try:
        resolved_secret = resolver.resolve(endpoint)
        headers = build_webhook_headers(
            delivery=delivery,
            endpoint=endpoint,
            integration_client=integration_client,
            resolved_secret=resolved_secret,
            body=body,
            timestamp=now,
        )
    except WebhookSigningSecretError as exc:
        return _mark_delivery_preflight_failed(delivery, failure_reason=str(exc))

    _mark_delivery_http_attempt_started(
        delivery,
        attempted_at=now,
        signing_secret_version=resolved_secret.version,
    )

    try:
        response = client.send(
            url=endpoint.url,
            headers=headers,
            body=body,
            timeout=endpoint.timeout_seconds,
        )
    except HTTPError as exc:
        response_body = exc.read(4096).decode("utf-8", errors="replace")
        return _mark_delivery_response(
            delivery,
            status_code=exc.code,
            body=response_body,
            attempted_at=now,
        )
    except (URLError, OSError) as exc:
        return _mark_delivery_transport_failed(
            delivery,
            failure_reason=_safe_failure_reason(exc),
            attempted_at=now,
        )

    return _mark_delivery_response(
        delivery,
        status_code=response.status_code,
        body=response.body,
        attempted_at=now,
    )


def _load_delivery(delivery_id):
    return (
        WebhookDelivery.objects.select_related(
            "event",
            "endpoint",
            "endpoint__integration_client",
        )
        .get(pk=delivery_id)
    )


def _claim_delivery_for_attempt(delivery_id, now):
    with transaction.atomic():
        delivery = (
            WebhookDelivery.objects.select_for_update()
            .select_related(
                "event",
                "endpoint",
                "endpoint__integration_client",
            )
            .get(pk=delivery_id)
        )
        if not _delivery_is_enqueueable(delivery, now):
            return None

        delivery.status = WebhookDelivery.Status.DELIVERING
        delivery.save(update_fields=("status", "updated_at"))
        return delivery


def build_webhook_headers(
    *,
    delivery,
    endpoint,
    integration_client,
    resolved_secret,
    body,
    timestamp,
):
    timestamp_text = timestamp.isoformat()
    signing_path = _signing_path(endpoint.url)
    signature = sign_webhook_request(
        secret=resolved_secret.value,
        method="POST",
        path=signing_path,
        timestamp=timestamp_text,
        body=body,
    )
    headers = {
        "Content-Type": "application/json",
        "X-OHTK-Event-ID": str(delivery.event.event_id),
        "X-OHTK-Tenant": _tenant_header_value(),
        "X-OHTK-Integration": integration_client.code,
        "X-OHTK-Timestamp": timestamp_text,
        "X-OHTK-Signature": signature,
        "X-OHTK-Signature-Alg": "HMAC-SHA256",
        "X-OHTK-Signing-Key-ID": resolved_secret.key_id,
        "X-OHTK-Signing-Secret-Version": str(resolved_secret.version),
    }
    headers.update(_normalise_custom_headers(endpoint.custom_headers))
    return headers


def sign_webhook_request(*, secret, method, path, timestamp, body):
    message = b"\n".join(
        [
            method.upper().encode("utf-8"),
            path.encode("utf-8"),
            timestamp.encode("utf-8"),
            body,
        ]
    )
    return hmac.new(
        secret.encode("utf-8"),
        message,
        hashlib.sha256,
    ).hexdigest()


def endpoint_is_deliverable(endpoint):
    return (
        endpoint.status == WebhookEndpoint.Status.ACTIVE
        and endpoint.deleted_at is None
        and endpoint.integration_client.is_active
    )


def _get_or_create_report_submitted_event(report):
    event_id = uuid.uuid4()
    produced_at = timezone.now()
    payload = build_report_submitted_payload(
        report=report,
        event_id=event_id,
        produced_at=produced_at,
    )

    event, _created = IntegrationEvent.objects.get_or_create(
        event_type=IntegrationEventType.REPORT_SUBMITTED,
        source_app="reports",
        subject_type="reports.IncidentReport",
        subject_id=str(report.id),
        defaults={
            "event_id": event_id,
            "schema_version": REPORT_SUBMITTED_SCHEMA_VERSION,
            "payload_hash": payload_hash(payload),
            "payload_summary": secret_safe_summary(
                payload,
                max_string_length=None,
                max_list_length=None,
            ),
            "produced_at": produced_at,
            "status": IntegrationEvent.Status.RECORDED,
        },
    )
    return event


def _create_missing_deliveries(event):
    endpoints = _active_subscribed_endpoints(event.event_type)
    with transaction.atomic():
        for endpoint in endpoints:
            WebhookDelivery.objects.get_or_create(
                event=event,
                endpoint=endpoint,
                defaults={
                    "payload_hash": event.payload_hash,
                    "signing_secret_version": endpoint.active_signing_secret_version,
                },
            )

def _deliveries_needing_enqueue(event):
    now = timezone.now()
    return [
        delivery
        for delivery in (
            WebhookDelivery.objects.select_related(
                "event",
                "endpoint",
                "endpoint__integration_client",
            )
            .filter(event=event)
            .filter(
                Q(status=WebhookDelivery.Status.PENDING)
                | Q(status=WebhookDelivery.Status.FAILED, next_retry_at__lte=now)
            )
            .order_by("id")
        )
        if _delivery_is_enqueueable(delivery, now)
        and _delivery_has_report_submitted_scope(delivery)
        and endpoint_is_deliverable(delivery.endpoint)
    ]


def _active_subscribed_endpoints(event_type):
    candidates = (
        WebhookEndpoint.objects.select_related("integration_client")
        .filter(
            status=WebhookEndpoint.Status.ACTIVE,
            integration_client__status=IntegrationClient.Status.ACTIVE,
            integration_client__deleted_at__isnull=True,
        )
        .order_by("id")
    )
    return [
        endpoint
        for endpoint in candidates
        if event_type in (endpoint.event_types or [])
        and _endpoint_has_report_submitted_scope(endpoint, event_type)
    ]


def _endpoint_has_report_submitted_scope(endpoint, event_type):
    if event_type != IntegrationEventType.REPORT_SUBMITTED:
        return True
    return endpoint.integration_client.has_scope(IntegrationScope.AI_READ_REPORT)


def _delivery_has_report_submitted_scope(delivery):
    return _endpoint_has_report_submitted_scope(
        delivery.endpoint,
        delivery.event.event_type,
    )


def _delivery_is_enqueueable(delivery, now):
    if delivery.attempt_count >= delivery.endpoint.max_attempts:
        return False
    if delivery.status == WebhookDelivery.Status.PENDING:
        return True
    if delivery.status != WebhookDelivery.Status.FAILED:
        return False
    if delivery.next_retry_at is None or delivery.next_retry_at > now:
        return False
    return True


def _mark_delivery_http_attempt_started(
    delivery,
    *,
    attempted_at,
    signing_secret_version,
):
    delivery.attempt_count += 1
    delivery.last_attempt_at = attempted_at
    delivery.next_retry_at = None
    delivery.response_status_code = None
    delivery.response_body_summary = {}
    delivery.signing_secret_version = signing_secret_version
    delivery.failure_reason = ""
    delivery.save(
        update_fields=(
            "attempt_count",
            "last_attempt_at",
            "next_retry_at",
            "response_status_code",
            "response_body_summary",
            "signing_secret_version",
            "failure_reason",
            "updated_at",
        )
    )


def _mark_delivery_response(delivery, *, status_code, body, attempted_at):
    successful = 200 <= status_code < 300
    delivery.status = (
        WebhookDelivery.Status.SUCCEEDED
        if successful
        else WebhookDelivery.Status.FAILED
    )
    delivery.response_status_code = status_code
    delivery.response_body_summary = _response_body_summary(body)
    delivery.next_retry_at = None if successful else _next_retry_at(delivery, attempted_at)
    delivery.failure_reason = "" if successful else f"HTTP {status_code}"
    delivery.save(
        update_fields=(
            "status",
            "response_status_code",
            "response_body_summary",
            "next_retry_at",
            "failure_reason",
            "updated_at",
        )
    )
    return delivery


def _mark_delivery_transport_failed(delivery, *, failure_reason, attempted_at):
    delivery.status = WebhookDelivery.Status.FAILED
    delivery.next_retry_at = _next_retry_at(delivery, attempted_at)
    delivery.failure_reason = failure_reason[:500]
    delivery.save(
        update_fields=(
            "status",
            "next_retry_at",
            "failure_reason",
            "updated_at",
        )
    )
    return delivery


def _mark_delivery_preflight_failed(delivery, *, failure_reason):
    delivery.status = WebhookDelivery.Status.FAILED
    delivery.next_retry_at = None
    delivery.response_status_code = None
    delivery.response_body_summary = {}
    delivery.failure_reason = failure_reason[:500]
    delivery.save(
        update_fields=(
            "status",
            "next_retry_at",
            "response_status_code",
            "response_body_summary",
            "failure_reason",
            "updated_at",
        )
    )
    return delivery


def _next_retry_at(delivery, attempted_at):
    if delivery.attempt_count >= delivery.endpoint.max_attempts:
        return None

    retry_policy = delivery.endpoint.retry_policy or {}
    delay_seconds = retry_policy.get("initial_delay_seconds", 300)
    return attempted_at + timedelta(seconds=delay_seconds)


def _response_body_summary(body):
    try:
        parsed = json.loads(body)
    except (TypeError, ValueError):
        return {
            "bodyLength": len(body or ""),
            "bodySha256": payload_hash(body or ""),
        }

    return secret_safe_summary(parsed, max_string_length=500, max_list_length=20)


def _safe_failure_reason(exc):
    return secret_safe_summary(str(exc), max_string_length=500)


def _serialize_json_body(payload):
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def _signing_path(url):
    parsed = urlsplit(url)
    path = parsed.path or "/"
    if parsed.query:
        return f"{path}?{parsed.query}"
    return path


def _tenant_payload():
    schema_name = getattr(connection, "schema_name", None)
    tenant = {"schema": schema_name}
    tenant_obj = getattr(connection, "tenant", None)
    if tenant_obj is not None:
        tenant["code"] = getattr(tenant_obj, "schema_name", schema_name)
        tenant_name = getattr(tenant_obj, "name", "")
        if tenant_name:
            tenant["name"] = tenant_name
    elif schema_name:
        tenant["code"] = schema_name
    return tenant


def _tenant_header_value():
    tenant_obj = getattr(connection, "tenant", None)
    if tenant_obj is not None:
        return getattr(tenant_obj, "schema_name", connection.schema_name)
    return getattr(connection, "schema_name", "")


def _isoformat_or_none(value):
    return value.isoformat() if value else None


def _normalise_custom_headers(custom_headers):
    headers = {}

    if isinstance(custom_headers, dict):
        for key, value in custom_headers.items():
            if key == "headers":
                headers.update(_normalise_custom_headers(value))
            elif isinstance(value, (str, int, float, bool)):
                headers[str(key)] = str(value)
    elif isinstance(custom_headers, list):
        for item in custom_headers:
            if not isinstance(item, dict):
                continue
            lowered_keys = {str(key).lower(): key for key in item.keys()}
            name_key = lowered_keys.get("name")
            value_key = lowered_keys.get("value")
            if name_key is not None and value_key is not None:
                headers[str(item[name_key])] = str(item[value_key])

    return {
        key: value
        for key, value in headers.items()
        if not key.lower().startswith("x-ohtk-")
        and key.lower() != "content-type"
    }
