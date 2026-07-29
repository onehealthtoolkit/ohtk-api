import json
import mimetypes
import uuid
from datetime import date
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import FileResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from oauth2_provider.oauth2_backends import OAuthLibCore
from oauth2_provider.oauth2_validators import OAuth2Validator
from oauthlib.oauth2 import Server

from accounts.models import Authority, Village
from census.models import (
    CensusDefinition,
    VillageCensusSnapshot,
)
from integrations.constants import IntegrationScope
from integrations.exceptions import (
    IntegrationClientDenied,
    IntegrationIdempotencyConflict,
    PublicSchemaDenied,
)
from integrations.models import (
    IntegrationActionLog,
    IntegrationClusterResult,
    IntegrationReportComment,
)
from integrations.models import RiskAssessment
from integrations.policy import (
    FEATURE_AI,
    FEATURE_CLUSTER_DETECTOR,
    FEATURE_RISK_EVALUATOR,
    IntegrationPolicyDenied,
    assert_integration_feature_enabled,
)
from integrations.services import (
    assert_integration_tenant_schema,
    claim_idempotency_key,
    create_integration_report_comment,
    create_risk_assessment,
    get_active_integration_client,
    get_current_risk_assessment,
)
from integrations.utils import payload_hash, secret_safe_summary
from reports.models import Image, IncidentReport


ACTION_INCIDENT_READ = "incident.read"
ACTION_CENSUS_READ = "census.read"
ACTION_AI_CREATE_COMMENT = "ai.create_comment"
ACTION_AI_READ_IMAGES = "ai.read_images"
ACTION_AI_READ_IMAGE_CONTENT = "ai.read_image_content"
ACTION_RISK_UPDATE = "risk.update"
ACTION_CLUSTER_WRITE_RESULT = "cluster.write_result"
ACTION_CLUSTER_READ = "cluster.read"
TARGET_REPORT = "reports.IncidentReport"
TARGET_REPORT_IMAGE = "reports.Image"
TARGET_CENSUS_SNAPSHOT = "census.VillageCensusSnapshot"
TARGET_VILLAGE = "accounts.Village"
TARGET_CLUSTER_RESULT = "integrations.IntegrationClusterResult"
TARGET_CLUSTER_EXTERNAL = "integrations.IntegrationClusterResult.externalClusterId"
SCHEMA_VERSION = "2026-06-02"
INCIDENT_LIST_DEFAULT_LIMIT = 50
INCIDENT_LIST_MAX_LIMIT = 100
INCIDENT_LIST_MAX_OFFSET = 10000
CENSUS_LIST_DEFAULT_LIMIT = 50
CENSUS_LIST_MAX_LIMIT = 100
CENSUS_LIST_MAX_OFFSET = 10000
CLUSTER_LIST_DEFAULT_LIMIT = 50
CLUSTER_LIST_MAX_LIMIT = 100
CLUSTER_LIST_MAX_OFFSET = 10000
CENSUS_LATEST_ALLOWED_QUERY_KEYS = {
    "villageId",
    "kind",
}
CENSUS_SNAPSHOT_ALLOWED_QUERY_KEYS = {
    "villageId",
    "kind",
    "from",
    "to",
    "limit",
    "offset",
}
INCIDENT_LIST_ALLOWED_QUERY_KEYS = {
    "from",
    "to",
    "authorityId",
    "includeChildAuthorities",
    "villageId",
    "reportTypeIds",
    "testFlag",
    "limit",
    "offset",
}
CLUSTER_LIST_ALLOWED_QUERY_KEYS = {
    "externalClusterId",
    "from",
    "to",
    "authorityId",
    "villageId",
    "riskLevel",
    "limit",
    "offset",
}
ALLOWED_COMMENT_PAYLOAD_KEYS = {
    "externalActionId",
    "body",
    "comment",
    "visibility",
    "metadata",
    "recommendation",
}
ALLOWED_RISK_PAYLOAD_KEYS = {
    "externalAssessmentId",
    "level",
    "score",
    "factors",
    "evaluatorVersion",
    "source",
}
ALLOWED_CLUSTER_PAYLOAD_KEYS = {
    "externalClusterId",
    "algorithmVersion",
    "window",
    "incidentIds",
    "authorityIds",
    "villageIds",
    "geometry",
    "radiusMeters",
    "score",
    "riskLevel",
    "explanation",
    "metadata",
}
ALLOWED_CLUSTER_WINDOW_KEYS = {"from", "to"}
INTEGRATION_RISK_SOURCES = {
    RiskAssessment.Source.EXTERNAL_RISK_EVALUATOR,
    RiskAssessment.Source.AI,
}


class _RiskReportNotFound(Exception):
    pass


class _IncidentFilterError(Exception):
    def __init__(self, message, code="invalid_query"):
        super().__init__(message)
        self.code = code


class _CensusFilterError(Exception):
    def __init__(self, message, code="invalid_query"):
        super().__init__(message)
        self.code = code


class _ClusterFilterError(Exception):
    def __init__(self, message, code="invalid_query"):
        super().__init__(message)
        self.code = code


class _ClusterExternalConflict(Exception):
    pass


@require_GET
def incidents(request):
    auth_response, integration_client = _authorize_incident_read_request(request)
    if auth_response is not None:
        return auth_response

    try:
        filters = _normalize_incident_list_filters(request.GET)
        reports = _incident_queryset_for_filters(filters)
        window = list(reports[filters["offset"] : filters["offset"] + filters["limit"] + 1])
        has_more = len(window) > filters["limit"]
        page_reports = window[: filters["limit"]]
        risk_assessments = _current_risk_assessments_by_report_id(
            [report.id for report in page_reports]
        )
        response_payload = {
            "schemaVersion": SCHEMA_VERSION,
            "dateFilter": {
                "field": "incident_date",
                "from": filters["from"],
                "to": filters["to"],
            },
            "pagination": {
                "limit": filters["limit"],
                "offset": filters["offset"],
                "count": len(page_reports),
                "nextOffset": filters["offset"] + filters["limit"]
                if has_more
                else None,
            },
            "incidents": [
                _incident_payload(
                    report,
                    current_risk_assessment=risk_assessments.get(str(report.id)),
                    include_links=True,
                )
                for report in page_reports
            ],
        }
        _create_incident_read_action_log(
            request=request,
            integration_client=integration_client,
            result_status=IntegrationActionLog.ResultStatus.ACCEPTED,
            result_summary={
                "response": {
                    "count": len(page_reports),
                    "nextOffset": response_payload["pagination"]["nextOffset"],
                },
                "querySummary": secret_safe_summary(_query_payload(request)),
            },
        )
        return JsonResponse(response_payload, status=200)
    except _IncidentFilterError as exc:
        _create_incident_read_action_log(
            request=request,
            integration_client=integration_client,
            result_status=IntegrationActionLog.ResultStatus.REJECTED,
            result_summary={
                "error": {
                    "code": exc.code,
                    "message": str(exc),
                },
                "querySummary": secret_safe_summary(_query_payload(request)),
            },
        )
        return _error_response(
            status=400,
            code=exc.code,
            message=str(exc),
        )
    except Exception:
        _create_incident_read_action_log(
            request=request,
            integration_client=integration_client,
            result_status=IntegrationActionLog.ResultStatus.FAILED,
            result_summary={
                "error": {
                    "code": "incident_read_failed",
                    "message": "Incident read failed.",
                },
                "querySummary": secret_safe_summary(_query_payload(request)),
            },
        )
        return _error_response(
            status=500,
            code="incident_read_failed",
            message="Incident read failed.",
        )


@require_GET
def incident_detail(request, report_id):
    target_id = str(report_id)
    auth_response, integration_client = _authorize_incident_read_request(
        request,
        target_id=target_id,
    )
    if auth_response is not None:
        return auth_response

    try:
        report = (
            IncidentReport.objects.select_related("report_type", "report_type__category")
            .prefetch_related("relevant_authorities")
            .get(pk=report_id)
        )
    except IncidentReport.DoesNotExist:
        _create_incident_read_action_log(
            request=request,
            integration_client=integration_client,
            target_id=target_id,
            result_status=IntegrationActionLog.ResultStatus.REJECTED,
            result_summary={
                "error": {
                    "code": "incident_not_found",
                    "message": "Incident was not found in the selected tenant.",
                },
                "querySummary": secret_safe_summary(_query_payload(request)),
            },
        )
        return _error_response(
            status=404,
            code="incident_not_found",
            message="Incident was not found in the selected tenant.",
        )

    try:
        current_risk_assessment = get_current_risk_assessment(report=report)
        response_payload = {
            "schemaVersion": SCHEMA_VERSION,
            "incident": _incident_payload(
                report,
                current_risk_assessment=current_risk_assessment,
            ),
            "links": _incident_links(report.id),
        }
        _create_incident_read_action_log(
            request=request,
            integration_client=integration_client,
            target_id=target_id,
            result_status=IntegrationActionLog.ResultStatus.ACCEPTED,
            result_summary={
                "response": {"incidentId": target_id},
                "querySummary": secret_safe_summary(_query_payload(request)),
            },
        )
        return JsonResponse(response_payload, status=200)
    except Exception:
        _create_incident_read_action_log(
            request=request,
            integration_client=integration_client,
            target_id=target_id,
            result_status=IntegrationActionLog.ResultStatus.FAILED,
            result_summary={
                "error": {
                    "code": "incident_read_failed",
                    "message": "Incident read failed.",
                },
                "querySummary": secret_safe_summary(_query_payload(request)),
            },
        )
        return _error_response(
            status=500,
            code="incident_read_failed",
            message="Incident read failed.",
        )


@require_GET
def census_latest(request):
    auth_response, integration_client = _authorize_census_read_request(request)
    if auth_response is not None:
        return auth_response

    try:
        filters = _normalize_census_query(
            request.GET,
            allowed_keys=CENSUS_LATEST_ALLOWED_QUERY_KEYS,
            include_window=False,
        )
        snapshot = _census_snapshot_queryset(filters).first()
        if snapshot is None:
            _create_census_read_action_log(
                request=request,
                integration_client=integration_client,
                target_type=TARGET_VILLAGE,
                target_id=str(filters["village"].id),
                result_status=IntegrationActionLog.ResultStatus.REJECTED,
                result_summary={
                    "error": {
                        "code": "census_snapshot_not_found",
                        "message": (
                            "No census snapshot was found for the selected "
                            "village and kind."
                        ),
                    },
                    "querySummary": secret_safe_summary(_query_payload(request)),
                },
            )
            return _error_response(
                status=404,
                code="census_snapshot_not_found",
                message=(
                    "No census snapshot was found for the selected village and kind."
                ),
            )

        response_payload = {
            "schemaVersion": SCHEMA_VERSION,
            "village": _village_payload(filters["village"]),
            "kind": filters["kind"],
            "snapshot": _census_snapshot_payload(snapshot, filters["kind"]),
        }
        _create_census_read_action_log(
            request=request,
            integration_client=integration_client,
            target_type=TARGET_CENSUS_SNAPSHOT,
            target_id=str(snapshot.id),
            result_status=IntegrationActionLog.ResultStatus.ACCEPTED,
            result_summary={
                "response": {
                    "snapshotId": snapshot.id,
                    "villageId": filters["village"].id,
                    "kind": filters["kind"],
                },
                "querySummary": secret_safe_summary(_query_payload(request)),
            },
        )
        return JsonResponse(response_payload, status=200)
    except _CensusFilterError as exc:
        _create_census_read_action_log(
            request=request,
            integration_client=integration_client,
            result_status=IntegrationActionLog.ResultStatus.REJECTED,
            result_summary={
                "error": {
                    "code": exc.code,
                    "message": str(exc),
                },
                "querySummary": secret_safe_summary(_query_payload(request)),
            },
        )
        return _error_response(
            status=400,
            code=exc.code,
            message=str(exc),
        )
    except Exception:
        _create_census_read_action_log(
            request=request,
            integration_client=integration_client,
            result_status=IntegrationActionLog.ResultStatus.FAILED,
            result_summary={
                "error": {
                    "code": "census_read_failed",
                    "message": "Census read failed.",
                },
                "querySummary": secret_safe_summary(_query_payload(request)),
            },
        )
        return _error_response(
            status=500,
            code="census_read_failed",
            message="Census read failed.",
        )


@require_GET
def census_snapshots(request):
    auth_response, integration_client = _authorize_census_read_request(request)
    if auth_response is not None:
        return auth_response

    try:
        filters = _normalize_census_query(
            request.GET,
            allowed_keys=CENSUS_SNAPSHOT_ALLOWED_QUERY_KEYS,
            include_window=True,
        )
        snapshots = _census_snapshot_queryset(filters)
        window = list(
            snapshots[filters["offset"] : filters["offset"] + filters["limit"] + 1]
        )
        has_more = len(window) > filters["limit"]
        page_snapshots = window[: filters["limit"]]
        response_payload = {
            "schemaVersion": SCHEMA_VERSION,
            "village": _village_payload(filters["village"]),
            "kind": filters["kind"],
            "dateFilter": {
                "field": "census_date",
                "from": filters["from"],
                "to": filters["to"],
            },
            "pagination": {
                "limit": filters["limit"],
                "offset": filters["offset"],
                "count": len(page_snapshots),
                "nextOffset": filters["offset"] + filters["limit"]
                if has_more
                else None,
            },
            "items": [
                _census_snapshot_payload(snapshot, filters["kind"])
                for snapshot in page_snapshots
            ],
        }
        _create_census_read_action_log(
            request=request,
            integration_client=integration_client,
            target_type=TARGET_VILLAGE,
            target_id=str(filters["village"].id),
            result_status=IntegrationActionLog.ResultStatus.ACCEPTED,
            result_summary={
                "response": {
                    "count": len(page_snapshots),
                    "nextOffset": response_payload["pagination"]["nextOffset"],
                    "villageId": filters["village"].id,
                    "kind": filters["kind"],
                },
                "querySummary": secret_safe_summary(_query_payload(request)),
            },
        )
        return JsonResponse(response_payload, status=200)
    except _CensusFilterError as exc:
        _create_census_read_action_log(
            request=request,
            integration_client=integration_client,
            result_status=IntegrationActionLog.ResultStatus.REJECTED,
            result_summary={
                "error": {
                    "code": exc.code,
                    "message": str(exc),
                },
                "querySummary": secret_safe_summary(_query_payload(request)),
            },
        )
        return _error_response(
            status=400,
            code=exc.code,
            message=str(exc),
        )
    except Exception:
        _create_census_read_action_log(
            request=request,
            integration_client=integration_client,
            result_status=IntegrationActionLog.ResultStatus.FAILED,
            result_summary={
                "error": {
                    "code": "census_read_failed",
                    "message": "Census read failed.",
                },
                "querySummary": secret_safe_summary(_query_payload(request)),
            },
        )
        return _error_response(
            status=500,
            code="census_read_failed",
            message="Census read failed.",
        )


@csrf_exempt
@require_http_methods(["GET", "POST"])
def clusters(request):
    if request.method == "GET":
        return _cluster_list(request)
    return _cluster_create(request)


@require_GET
def cluster_detail(request, cluster_id):
    target_id = str(cluster_id)
    auth_response, integration_client = _authorize_cluster_request(
        request,
        action_type=ACTION_CLUSTER_READ,
        target_type=TARGET_CLUSTER_RESULT,
        target_id=target_id,
    )
    if auth_response is not None:
        return auth_response

    try:
        cluster = IntegrationClusterResult.objects.select_related(
            "integration_client"
        ).get(
            cluster_id=cluster_id,
            integration_client=integration_client,
        )
    except IntegrationClusterResult.DoesNotExist:
        _create_cluster_action_log(
            request=request,
            integration_client=integration_client,
            action_type=ACTION_CLUSTER_READ,
            target_type=TARGET_CLUSTER_RESULT,
            target_id=target_id,
            result_status=IntegrationActionLog.ResultStatus.REJECTED,
            result_summary={
                "error": {
                    "code": "cluster_not_found",
                    "message": "Cluster result was not found in the selected tenant.",
                },
                "querySummary": secret_safe_summary(_query_payload(request)),
            },
        )
        return _error_response(
            status=404,
            code="cluster_not_found",
            message="Cluster result was not found in the selected tenant.",
        )

    try:
        response_payload = {
            "schemaVersion": SCHEMA_VERSION,
            "cluster": _cluster_payload(cluster),
        }
        _create_cluster_action_log(
            request=request,
            integration_client=integration_client,
            action_type=ACTION_CLUSTER_READ,
            target_type=TARGET_CLUSTER_RESULT,
            target_id=target_id,
            result_status=IntegrationActionLog.ResultStatus.ACCEPTED,
            result_summary={
                "response": {
                    "clusterId": target_id,
                    "externalClusterId": cluster.external_cluster_id,
                },
                "querySummary": secret_safe_summary(_query_payload(request)),
            },
        )
        return JsonResponse(response_payload, status=200)
    except Exception:
        _create_cluster_action_log(
            request=request,
            integration_client=integration_client,
            action_type=ACTION_CLUSTER_READ,
            target_type=TARGET_CLUSTER_RESULT,
            target_id=target_id,
            result_status=IntegrationActionLog.ResultStatus.FAILED,
            result_summary={
                "error": {
                    "code": "cluster_read_failed",
                    "message": "Cluster result read failed.",
                },
                "querySummary": secret_safe_summary(_query_payload(request)),
            },
        )
        return _error_response(
            status=500,
            code="cluster_read_failed",
            message="Cluster result read failed.",
        )


def _cluster_list(request):
    auth_response, integration_client = _authorize_cluster_request(
        request,
        action_type=ACTION_CLUSTER_READ,
    )
    if auth_response is not None:
        return auth_response

    try:
        filters = _normalize_cluster_list_filters(request.GET)
        clusters_queryset = _cluster_queryset_for_filters(
            filters,
            integration_client=integration_client,
        )
        window = list(
            clusters_queryset[
                filters["offset"] : filters["offset"] + filters["limit"] + 1
            ]
        )
        has_more = len(window) > filters["limit"]
        page_clusters = window[: filters["limit"]]
        response_payload = {
            "schemaVersion": SCHEMA_VERSION,
            "dateFilter": {
                "field": "window_overlap",
                "from": filters["from"],
                "to": filters["to"],
            },
            "pagination": {
                "limit": filters["limit"],
                "offset": filters["offset"],
                "count": len(page_clusters),
                "nextOffset": filters["offset"] + filters["limit"]
                if has_more
                else None,
            },
            "clusters": [_cluster_payload(cluster) for cluster in page_clusters],
        }
        _create_cluster_action_log(
            request=request,
            integration_client=integration_client,
            action_type=ACTION_CLUSTER_READ,
            result_status=IntegrationActionLog.ResultStatus.ACCEPTED,
            result_summary={
                "response": {
                    "count": len(page_clusters),
                    "nextOffset": response_payload["pagination"]["nextOffset"],
                },
                "querySummary": secret_safe_summary(_query_payload(request)),
            },
        )
        return JsonResponse(response_payload, status=200)
    except _ClusterFilterError as exc:
        _create_cluster_action_log(
            request=request,
            integration_client=integration_client,
            action_type=ACTION_CLUSTER_READ,
            result_status=IntegrationActionLog.ResultStatus.REJECTED,
            result_summary={
                "error": {
                    "code": exc.code,
                    "message": str(exc),
                },
                "querySummary": secret_safe_summary(_query_payload(request)),
            },
        )
        return _error_response(
            status=400,
            code=exc.code,
            message=str(exc),
        )
    except Exception:
        _create_cluster_action_log(
            request=request,
            integration_client=integration_client,
            action_type=ACTION_CLUSTER_READ,
            result_status=IntegrationActionLog.ResultStatus.FAILED,
            result_summary={
                "error": {
                    "code": "cluster_read_failed",
                    "message": "Cluster result read failed.",
                },
                "querySummary": secret_safe_summary(_query_payload(request)),
            },
        )
        return _error_response(
            status=500,
            code="cluster_read_failed",
            message="Cluster result read failed.",
        )


def _cluster_create(request):
    auth_response, integration_client = _authorize_cluster_request(
        request,
        action_type=ACTION_CLUSTER_WRITE_RESULT,
    )
    if auth_response is not None:
        return auth_response

    payload, parse_error = _parse_json_body(request)
    if parse_error:
        _create_cluster_action_log(
            request=request,
            integration_client=integration_client,
            action_type=ACTION_CLUSTER_WRITE_RESULT,
            raw_payload=request.body,
            result_status=IntegrationActionLog.ResultStatus.REJECTED,
            result_summary={
                "error": {
                    "code": "invalid_json",
                    "message": parse_error,
                },
                "payloadSummary": {"rawBody": "[invalid-json]"},
            },
        )
        return _error_response(
            status=400,
            code="invalid_json",
            message=parse_error,
        )

    normalized, validation_error = _normalize_cluster_payload(payload)
    idempotency_key = _cluster_idempotency_key(request, normalized)
    if validation_error is None and not idempotency_key:
        validation_error = (
            "Idempotency-Key header or body externalClusterId is required."
        )
    if validation_error is None and len(idempotency_key) > 200:
        validation_error = "Idempotency key must be 200 characters or fewer."

    if validation_error:
        _create_cluster_action_log(
            request=request,
            integration_client=integration_client,
            action_type=ACTION_CLUSTER_WRITE_RESULT,
            target_type=TARGET_CLUSTER_EXTERNAL,
            target_id=normalized.get("external_cluster_id", ""),
            payload=payload,
            idempotency_key=idempotency_key,
            external_cluster_id=normalized.get("external_cluster_id", ""),
            result_status=IntegrationActionLog.ResultStatus.REJECTED,
            result_summary={
                "error": {
                    "code": "invalid_payload",
                    "message": validation_error,
                },
                "payloadSummary": secret_safe_summary(payload),
            },
        )
        return _error_response(
            status=400,
            code="invalid_payload",
            message=validation_error,
        )

    try:
        with transaction.atomic():
            idempotency = claim_idempotency_key(
                integration_client=integration_client,
                action_type=ACTION_CLUSTER_WRITE_RESULT,
                key=idempotency_key,
                request_payload=payload,
                target_type=TARGET_CLUSTER_EXTERNAL,
                target_id=normalized["external_cluster_id"],
            )
            if idempotency.replayed:
                response_payload = _replayed_payload(idempotency.record.response_summary)
                response_status = idempotency.record.response_status_code or 202
                response_cluster = response_payload.get("cluster", {})
                _create_cluster_action_log(
                    request=request,
                    integration_client=integration_client,
                    action_type=ACTION_CLUSTER_WRITE_RESULT,
                    target_type=TARGET_CLUSTER_RESULT,
                    target_id=response_cluster.get("id", ""),
                    payload=payload,
                    idempotency_key=idempotency_key,
                    external_cluster_id=normalized["external_cluster_id"],
                    result_status=IntegrationActionLog.ResultStatus.REPLAYED,
                    result_summary={
                        "response": response_payload,
                        "payloadSummary": secret_safe_summary(payload),
                        "originalActionLogId": _action_id_for_record(
                            idempotency.record
                        ),
                    },
                )
                return JsonResponse(response_payload, status=response_status)

            if IntegrationClusterResult.objects.filter(
                integration_client=integration_client,
                external_cluster_id=normalized["external_cluster_id"],
            ).exists():
                raise _ClusterExternalConflict(
                    "externalClusterId already exists for this integration client."
                )

            cluster = IntegrationClusterResult.objects.create(
                integration_client=integration_client,
                external_cluster_id=normalized["external_cluster_id"],
                algorithm_version=normalized["algorithm_version"],
                window_start=normalized["window_start"],
                window_end=normalized["window_end"],
                incident_ids=normalized["incident_ids"],
                authority_ids=normalized["authority_ids"],
                village_ids=normalized["village_ids"],
                geometry=normalized["geometry"],
                radius_meters=normalized["radius_meters"],
                score=normalized["score"],
                risk_level=normalized["risk_level"],
                explanation=normalized["explanation"],
                metadata=normalized["metadata"],
            )
            response_payload = _cluster_write_payload(cluster)
            action_log = _create_cluster_action_log(
                request=request,
                integration_client=integration_client,
                action_type=ACTION_CLUSTER_WRITE_RESULT,
                target_type=TARGET_CLUSTER_RESULT,
                target_id=str(cluster.cluster_id),
                payload=payload,
                idempotency_key=idempotency_key,
                external_cluster_id=normalized["external_cluster_id"],
                result_status=IntegrationActionLog.ResultStatus.ACCEPTED,
                result_summary={
                    "response": response_payload,
                    "payloadSummary": secret_safe_summary(payload),
                },
            )
            cluster.action_log = action_log
            cluster.save(update_fields=("action_log", "updated_at"))
            idempotency.record.response_status_code = 202
            idempotency.record.response_summary = response_payload
            idempotency.record.action_log = action_log
            idempotency.record.save(
                update_fields=(
                    "response_status_code",
                    "response_summary",
                    "action_log",
                    "updated_at",
                )
            )
    except IntegrationIdempotencyConflict as exc:
        _create_cluster_action_log(
            request=request,
            integration_client=integration_client,
            action_type=ACTION_CLUSTER_WRITE_RESULT,
            target_type=TARGET_CLUSTER_EXTERNAL,
            target_id=normalized["external_cluster_id"],
            payload=payload,
            idempotency_key=idempotency_key,
            external_cluster_id=normalized["external_cluster_id"],
            result_status=IntegrationActionLog.ResultStatus.REJECTED,
            result_summary={
                "error": {
                    "code": "idempotency_conflict",
                    "message": str(exc),
                },
                "payloadSummary": secret_safe_summary(payload),
            },
        )
        return _error_response(
            status=409,
            code="idempotency_conflict",
            message=str(exc),
        )
    except _ClusterExternalConflict as exc:
        _create_cluster_action_log(
            request=request,
            integration_client=integration_client,
            action_type=ACTION_CLUSTER_WRITE_RESULT,
            target_type=TARGET_CLUSTER_EXTERNAL,
            target_id=normalized["external_cluster_id"],
            payload=payload,
            idempotency_key=idempotency_key,
            external_cluster_id=normalized["external_cluster_id"],
            result_status=IntegrationActionLog.ResultStatus.REJECTED,
            result_summary={
                "error": {
                    "code": "cluster_result_conflict",
                    "message": str(exc),
                },
                "payloadSummary": secret_safe_summary(payload),
            },
        )
        return _error_response(
            status=409,
            code="cluster_result_conflict",
            message=str(exc),
        )
    except IntegrityError as exc:
        if _is_cluster_external_unique_conflict(exc):
            _create_cluster_action_log(
                request=request,
                integration_client=integration_client,
                action_type=ACTION_CLUSTER_WRITE_RESULT,
                target_type=TARGET_CLUSTER_EXTERNAL,
                target_id=normalized["external_cluster_id"],
                payload=payload,
                idempotency_key=idempotency_key,
                external_cluster_id=normalized["external_cluster_id"],
                result_status=IntegrationActionLog.ResultStatus.REJECTED,
                result_summary={
                    "error": {
                        "code": "cluster_result_conflict",
                        "message": (
                            "externalClusterId already exists for this "
                            "integration client."
                        ),
                    },
                    "payloadSummary": secret_safe_summary(payload),
                },
            )
            return _error_response(
                status=409,
                code="cluster_result_conflict",
                message=(
                    "externalClusterId already exists for this integration client."
                ),
            )

        _create_cluster_action_log(
            request=request,
            integration_client=integration_client,
            action_type=ACTION_CLUSTER_WRITE_RESULT,
            target_type=TARGET_CLUSTER_EXTERNAL,
            target_id=normalized["external_cluster_id"],
            payload=payload,
            idempotency_key=idempotency_key,
            external_cluster_id=normalized["external_cluster_id"],
            result_status=IntegrationActionLog.ResultStatus.REJECTED,
            result_summary={
                "error": {
                    "code": "invalid_payload",
                    "message": str(exc),
                },
                "payloadSummary": secret_safe_summary(payload),
            },
        )
        return _error_response(
            status=400,
            code="invalid_payload",
            message=str(exc),
        )
    except ValidationError as exc:
        _create_cluster_action_log(
            request=request,
            integration_client=integration_client,
            action_type=ACTION_CLUSTER_WRITE_RESULT,
            target_type=TARGET_CLUSTER_EXTERNAL,
            target_id=normalized["external_cluster_id"],
            payload=payload,
            idempotency_key=idempotency_key,
            external_cluster_id=normalized["external_cluster_id"],
            result_status=IntegrationActionLog.ResultStatus.REJECTED,
            result_summary={
                "error": {
                    "code": "invalid_payload",
                    "message": str(exc),
                },
                "payloadSummary": secret_safe_summary(payload),
            },
        )
        return _error_response(
            status=400,
            code="invalid_payload",
            message=str(exc),
        )
    except Exception:
        _create_cluster_action_log(
            request=request,
            integration_client=integration_client,
            action_type=ACTION_CLUSTER_WRITE_RESULT,
            target_type=TARGET_CLUSTER_EXTERNAL,
            target_id=normalized["external_cluster_id"],
            payload=payload,
            idempotency_key=idempotency_key,
            external_cluster_id=normalized["external_cluster_id"],
            result_status=IntegrationActionLog.ResultStatus.FAILED,
            result_summary={
                "error": {
                    "code": "cluster_write_failed",
                    "message": "Cluster result write failed.",
                },
                "payloadSummary": secret_safe_summary(payload),
            },
        )
        return _error_response(
            status=500,
            code="cluster_write_failed",
            message="Cluster result write failed.",
        )

    return JsonResponse(response_payload, status=202)


@require_GET
def report_images(request, report_id):
    target_id = str(report_id)
    auth_response, integration_client = _authorize_ai_image_read_request(
        request,
        action_type=ACTION_AI_READ_IMAGES,
        target_type=TARGET_REPORT,
        target_id=target_id,
    )
    if auth_response is not None:
        return auth_response

    try:
        report = IncidentReport.objects.get(pk=report_id)
    except IncidentReport.DoesNotExist:
        _create_ai_image_action_log(
            request=request,
            integration_client=integration_client,
            action_type=ACTION_AI_READ_IMAGES,
            target_type=TARGET_REPORT,
            target_id=target_id,
            result_status=IntegrationActionLog.ResultStatus.REJECTED,
            result_summary={
                "error": {
                    "code": "incident_not_found",
                    "message": "Incident was not found in the selected tenant.",
                },
            },
        )
        return _error_response(
            status=404,
            code="incident_not_found",
            message="Incident was not found in the selected tenant.",
        )

    try:
        images = _ordered_report_images(report)
        response_payload = {
            "schemaVersion": SCHEMA_VERSION,
            "reportId": target_id,
            "images": [
                _image_metadata_payload(image, report=report) for image in images
            ],
            "links": {
                "incident": f"/api/integrations/v1/incidents/{report.id}",
                "comments": f"/api/integrations/v1/reports/{report.id}/comments",
            },
        }
        _create_ai_image_action_log(
            request=request,
            integration_client=integration_client,
            action_type=ACTION_AI_READ_IMAGES,
            target_type=TARGET_REPORT,
            target_id=target_id,
            result_status=IntegrationActionLog.ResultStatus.ACCEPTED,
            result_summary={
                "response": {
                    "reportId": target_id,
                    "imageCount": len(response_payload["images"]),
                },
            },
        )
        return JsonResponse(response_payload, status=200)
    except Exception:
        _create_ai_image_action_log(
            request=request,
            integration_client=integration_client,
            action_type=ACTION_AI_READ_IMAGES,
            target_type=TARGET_REPORT,
            target_id=target_id,
            result_status=IntegrationActionLog.ResultStatus.FAILED,
            result_summary={
                "error": {
                    "code": "image_list_failed",
                    "message": "Report image list failed.",
                },
            },
        )
        return _error_response(
            status=500,
            code="image_list_failed",
            message="Report image list failed.",
        )


@require_GET
def report_image_content(request, report_id, image_id):
    report_target_id = str(report_id)
    image_target_id = str(image_id)
    auth_response, integration_client = _authorize_ai_image_read_request(
        request,
        action_type=ACTION_AI_READ_IMAGE_CONTENT,
        target_type=TARGET_REPORT_IMAGE,
        target_id=image_target_id,
    )
    if auth_response is not None:
        return auth_response

    try:
        report = IncidentReport.objects.get(pk=report_id)
    except IncidentReport.DoesNotExist:
        _create_ai_image_action_log(
            request=request,
            integration_client=integration_client,
            action_type=ACTION_AI_READ_IMAGE_CONTENT,
            target_type=TARGET_REPORT,
            target_id=report_target_id,
            result_status=IntegrationActionLog.ResultStatus.REJECTED,
            result_summary={
                "error": {
                    "code": "incident_not_found",
                    "message": "Incident was not found in the selected tenant.",
                },
            },
        )
        return _error_response(
            status=404,
            code="incident_not_found",
            message="Incident was not found in the selected tenant.",
        )

    try:
        image = report.images.get(pk=image_id)
    except Image.DoesNotExist:
        _create_ai_image_action_log(
            request=request,
            integration_client=integration_client,
            action_type=ACTION_AI_READ_IMAGE_CONTENT,
            target_type=TARGET_REPORT_IMAGE,
            target_id=image_target_id,
            result_status=IntegrationActionLog.ResultStatus.REJECTED,
            result_summary={
                "error": {
                    "code": "image_not_found",
                    "message": "Image was not found for the selected report.",
                },
            },
        )
        return _error_response(
            status=404,
            code="image_not_found",
            message="Image was not found for the selected report.",
        )

    try:
        if not image.file or not image.file.name:
            raise FileNotFoundError("Image file is missing.")
        # Resolve MIME before opening the stream handle so sniffing cannot
        # close the same FieldFile instance used by FileResponse.
        content_type = _image_content_type(image)
        file_handle = image.file.open("rb")
        response = FileResponse(
            file_handle,
            content_type=content_type,
            as_attachment=False,
            filename=str(image.id),
        )
        response["Cache-Control"] = "private, no-store"
        response["Content-Disposition"] = f'inline; filename="{image.id}"'
        byte_size = _image_byte_size(image)
        if byte_size is not None:
            response["Content-Length"] = str(byte_size)
        _create_ai_image_action_log(
            request=request,
            integration_client=integration_client,
            action_type=ACTION_AI_READ_IMAGE_CONTENT,
            target_type=TARGET_REPORT_IMAGE,
            target_id=image_target_id,
            result_status=IntegrationActionLog.ResultStatus.ACCEPTED,
            result_summary={
                "response": {
                    "reportId": report_target_id,
                    "imageId": image_target_id,
                    "contentType": content_type,
                    "byteSize": byte_size,
                },
            },
        )
        return response
    except FileNotFoundError:
        _create_ai_image_action_log(
            request=request,
            integration_client=integration_client,
            action_type=ACTION_AI_READ_IMAGE_CONTENT,
            target_type=TARGET_REPORT_IMAGE,
            target_id=image_target_id,
            result_status=IntegrationActionLog.ResultStatus.REJECTED,
            result_summary={
                "error": {
                    "code": "image_not_found",
                    "message": "Image file is missing for the selected report.",
                },
            },
        )
        return _error_response(
            status=404,
            code="image_not_found",
            message="Image file is missing for the selected report.",
        )
    except Exception:
        _create_ai_image_action_log(
            request=request,
            integration_client=integration_client,
            action_type=ACTION_AI_READ_IMAGE_CONTENT,
            target_type=TARGET_REPORT_IMAGE,
            target_id=image_target_id,
            result_status=IntegrationActionLog.ResultStatus.FAILED,
            result_summary={
                "error": {
                    "code": "image_read_failed",
                    "message": "Report image content read failed.",
                },
            },
        )
        return _error_response(
            status=500,
            code="image_read_failed",
            message="Report image content read failed.",
        )


@csrf_exempt
@require_POST
def report_comments(request, report_id):
    target_id = str(report_id)

    try:
        assert_integration_tenant_schema()
    except PublicSchemaDenied as exc:
        return _error_response(
            status=403,
            code="tenant_denied",
            message=str(exc),
        )

    oauth_context = _verify_oauth_context(request)
    if oauth_context is None:
        return _error_response(
            status=401,
            code="oauth_required",
            message="A valid OAuth2 bearer token is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    oauth_application = oauth_context["application"]
    oauth_user = oauth_context["user"]
    try:
        auth_context = get_active_integration_client(oauth_application)
    except (PublicSchemaDenied, IntegrationClientDenied) as exc:
        return _error_response(
            status=403,
            code="integration_client_denied",
            message=str(exc),
        )

    integration_client = auth_context.integration_client
    if oauth_user is not None:
        _create_action_log(
            request=request,
            integration_client=integration_client,
            target_id=target_id,
            result_status=IntegrationActionLog.ResultStatus.REJECTED,
            result_summary={
                "error": {
                    "code": "service_identity_denied",
                    "message": (
                        "Integration endpoints require service OAuth tokens "
                        "without a human user."
                    ),
                }
            },
        )
        return _error_response(
            status=403,
            code="service_identity_denied",
            message=(
                "Integration endpoints require service OAuth tokens without a "
                "human user."
            ),
        )

    if not integration_client.has_scope(IntegrationScope.AI_CREATE_COMMENT):
        _create_action_log(
            request=request,
            integration_client=integration_client,
            target_id=target_id,
            result_status=IntegrationActionLog.ResultStatus.REJECTED,
            result_summary={
                "error": {
                    "code": "scope_denied",
                    "message": (
                        "Integration client lacks required scope: "
                        f"{IntegrationScope.AI_CREATE_COMMENT}"
                    ),
                }
            },
        )
        return _error_response(
            status=403,
            code="scope_denied",
            message=(
                "Integration client lacks required scope: "
                f"{IntegrationScope.AI_CREATE_COMMENT}"
            ),
        )

    try:
        assert_integration_feature_enabled(FEATURE_AI)
    except IntegrationPolicyDenied as exc:
        _create_action_log(
            request=request,
            integration_client=integration_client,
            target_id=target_id,
            result_status=IntegrationActionLog.ResultStatus.REJECTED,
            result_summary={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                }
            },
        )
        return _error_response(status=403, code=exc.code, message=exc.message)

    payload, parse_error = _parse_json_body(request)
    if parse_error:
        _create_action_log(
            request=request,
            integration_client=integration_client,
            target_id=target_id,
            raw_payload=request.body,
            result_status=IntegrationActionLog.ResultStatus.REJECTED,
            result_summary={
                "error": {
                    "code": "invalid_json",
                    "message": parse_error,
                },
                "payloadSummary": {"rawBody": "[invalid-json]"},
            },
        )
        return _error_response(
            status=400,
            code="invalid_json",
            message=parse_error,
        )

    normalized, validation_error = _normalize_comment_payload(payload)
    idempotency_key = _idempotency_key(request, normalized)
    if validation_error is None and not idempotency_key:
        validation_error = (
            "Idempotency-Key header or body externalActionId is required."
        )
    if validation_error is None and len(idempotency_key) > 200:
        validation_error = "Idempotency key must be 200 characters or fewer."

    if validation_error:
        _create_action_log(
            request=request,
            integration_client=integration_client,
            target_id=target_id,
            payload=payload,
            idempotency_key=idempotency_key,
            external_action_id=normalized.get("external_action_id", ""),
            result_status=IntegrationActionLog.ResultStatus.REJECTED,
            result_summary={
                "error": {
                    "code": "invalid_payload",
                    "message": validation_error,
                },
                "payloadSummary": secret_safe_summary(payload),
            },
        )
        return _error_response(
            status=400,
            code="invalid_payload",
            message=validation_error,
        )

    try:
        report = IncidentReport.objects.get(pk=report_id)
    except IncidentReport.DoesNotExist:
        _create_action_log(
            request=request,
            integration_client=integration_client,
            target_id=target_id,
            payload=payload,
            idempotency_key=idempotency_key,
            external_action_id=normalized["external_action_id"],
            result_status=IntegrationActionLog.ResultStatus.REJECTED,
            result_summary={
                "error": {
                    "code": "report_not_found",
                    "message": "Report was not found in the selected tenant.",
                },
                "payloadSummary": secret_safe_summary(payload),
            },
        )
        return _error_response(
            status=404,
            code="report_not_found",
            message="Report was not found in the selected tenant.",
        )

    try:
        with transaction.atomic():
            idempotency = claim_idempotency_key(
                integration_client=integration_client,
                action_type=ACTION_AI_CREATE_COMMENT,
                key=idempotency_key,
                request_payload=payload,
                target_type=TARGET_REPORT,
                target_id=target_id,
            )
            if idempotency.replayed:
                response_payload = idempotency.record.response_summary
                response_status = idempotency.record.response_status_code or 202
                _create_action_log(
                    request=request,
                    integration_client=integration_client,
                    target_id=target_id,
                    payload=payload,
                    idempotency_key=idempotency_key,
                    external_action_id=normalized["external_action_id"],
                    result_status=IntegrationActionLog.ResultStatus.REPLAYED,
                    result_summary={
                        "response": response_payload,
                        "payloadSummary": secret_safe_summary(payload),
                        "originalActionLogId": _action_id_for_record(
                            idempotency.record
                        ),
                    },
                )
                return JsonResponse(response_payload, status=response_status)

            comment = create_integration_report_comment(
                report=report,
                integration_client=integration_client,
                body=normalized["body"],
                visibility=normalized["visibility"],
                external_action_id=normalized["external_action_id"],
                metadata=normalized["metadata"],
                recommendation=normalized["recommendation"],
            )
            response_payload = _accepted_payload(comment)
            action_log = _create_action_log(
                request=request,
                integration_client=integration_client,
                target_id=target_id,
                payload=payload,
                idempotency_key=idempotency_key,
                external_action_id=normalized["external_action_id"],
                result_status=IntegrationActionLog.ResultStatus.ACCEPTED,
                result_summary={
                    "response": response_payload,
                    "payloadSummary": secret_safe_summary(payload),
                },
            )
            idempotency.record.response_status_code = 202
            idempotency.record.response_summary = response_payload
            idempotency.record.action_log = action_log
            idempotency.record.save(
                update_fields=(
                    "response_status_code",
                    "response_summary",
                    "action_log",
                    "updated_at",
                )
            )
    except IntegrationIdempotencyConflict as exc:
        _create_action_log(
            request=request,
            integration_client=integration_client,
            target_id=target_id,
            payload=payload,
            idempotency_key=idempotency_key,
            external_action_id=normalized["external_action_id"],
            result_status=IntegrationActionLog.ResultStatus.REJECTED,
            result_summary={
                "error": {
                    "code": "idempotency_conflict",
                    "message": str(exc),
                },
                "payloadSummary": secret_safe_summary(payload),
            },
        )
        return _error_response(
            status=409,
            code="idempotency_conflict",
            message=str(exc),
        )
    except ValidationError as exc:
        _create_action_log(
            request=request,
            integration_client=integration_client,
            target_id=target_id,
            payload=payload,
            idempotency_key=idempotency_key,
            external_action_id=normalized["external_action_id"],
            result_status=IntegrationActionLog.ResultStatus.REJECTED,
            result_summary={
                "error": {
                    "code": "invalid_payload",
                    "message": str(exc),
                },
                "payloadSummary": secret_safe_summary(payload),
            },
        )
        return _error_response(
            status=400,
            code="invalid_payload",
            message=str(exc),
        )

    return JsonResponse(response_payload, status=202)


@csrf_exempt
@require_POST
def report_risk_assessments(request, report_id):
    target_id = str(report_id)

    try:
        assert_integration_tenant_schema()
    except PublicSchemaDenied as exc:
        return _error_response(
            status=403,
            code="tenant_denied",
            message=str(exc),
        )

    oauth_context = _verify_oauth_context(request)
    if oauth_context is None:
        return _error_response(
            status=401,
            code="oauth_required",
            message="A valid OAuth2 bearer token is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    oauth_application = oauth_context["application"]
    oauth_user = oauth_context["user"]
    try:
        auth_context = get_active_integration_client(oauth_application)
    except (PublicSchemaDenied, IntegrationClientDenied) as exc:
        return _error_response(
            status=403,
            code="integration_client_denied",
            message=str(exc),
        )

    integration_client = auth_context.integration_client
    if oauth_user is not None:
        _create_risk_action_log(
            request=request,
            integration_client=integration_client,
            target_type=TARGET_REPORT,
            target_id=target_id,
            result_status=IntegrationActionLog.ResultStatus.REJECTED,
            result_summary={
                "error": {
                    "code": "service_identity_denied",
                    "message": (
                        "Integration endpoints require service OAuth tokens "
                        "without a human user."
                    ),
                }
            },
        )
        return _error_response(
            status=403,
            code="service_identity_denied",
            message=(
                "Integration endpoints require service OAuth tokens without a "
                "human user."
            ),
        )

    if not integration_client.has_scope(IntegrationScope.RISK_UPDATE):
        _create_risk_action_log(
            request=request,
            integration_client=integration_client,
            target_type=TARGET_REPORT,
            target_id=target_id,
            result_status=IntegrationActionLog.ResultStatus.REJECTED,
            result_summary={
                "error": {
                    "code": "scope_denied",
                    "message": (
                        "Integration client lacks required scope: "
                        f"{IntegrationScope.RISK_UPDATE}"
                    ),
                }
            },
        )
        return _error_response(
            status=403,
            code="scope_denied",
            message=(
                "Integration client lacks required scope: "
                f"{IntegrationScope.RISK_UPDATE}"
            ),
        )

    try:
        assert_integration_feature_enabled(FEATURE_RISK_EVALUATOR)
    except IntegrationPolicyDenied as exc:
        _create_risk_action_log(
            request=request,
            integration_client=integration_client,
            target_type=TARGET_REPORT,
            target_id=target_id,
            result_status=IntegrationActionLog.ResultStatus.REJECTED,
            result_summary={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                }
            },
        )
        return _error_response(status=403, code=exc.code, message=exc.message)

    payload, parse_error = _parse_json_body(request)
    if parse_error:
        _create_risk_action_log(
            request=request,
            integration_client=integration_client,
            target_type=TARGET_REPORT,
            target_id=target_id,
            raw_payload=request.body,
            result_status=IntegrationActionLog.ResultStatus.REJECTED,
            result_summary={
                "error": {
                    "code": "invalid_json",
                    "message": parse_error,
                },
                "payloadSummary": {"rawBody": "[invalid-json]"},
            },
        )
        return _error_response(
            status=400,
            code="invalid_json",
            message=parse_error,
        )

    normalized, validation_error = _normalize_risk_payload(payload)
    idempotency_key = _risk_idempotency_key(request, normalized)
    if validation_error is None and not idempotency_key:
        validation_error = (
            "Idempotency-Key header or body externalAssessmentId is required."
        )
    if validation_error is None and len(idempotency_key) > 200:
        validation_error = "Idempotency key must be 200 characters or fewer."

    if validation_error:
        _create_risk_action_log(
            request=request,
            integration_client=integration_client,
            target_type=TARGET_REPORT,
            target_id=target_id,
            payload=payload,
            idempotency_key=idempotency_key,
            external_assessment_id=normalized.get("external_assessment_id", ""),
            result_status=IntegrationActionLog.ResultStatus.REJECTED,
            result_summary={
                "error": {
                    "code": "invalid_payload",
                    "message": validation_error,
                },
                "payloadSummary": secret_safe_summary(payload),
            },
        )
        return _error_response(
            status=400,
            code="invalid_payload",
            message=validation_error,
        )

    try:
        with transaction.atomic():
            idempotency = claim_idempotency_key(
                integration_client=integration_client,
                action_type=ACTION_RISK_UPDATE,
                key=idempotency_key,
                request_payload=payload,
                target_type=TARGET_REPORT,
                target_id=target_id,
            )
            if idempotency.replayed:
                response_payload = _replayed_payload(idempotency.record.response_summary)
                response_status = idempotency.record.response_status_code or 202
                _create_risk_action_log(
                    request=request,
                    integration_client=integration_client,
                    target_type=TARGET_REPORT,
                    target_id=target_id,
                    payload=payload,
                    idempotency_key=idempotency_key,
                    external_assessment_id=normalized["external_assessment_id"],
                    result_status=IntegrationActionLog.ResultStatus.REPLAYED,
                    result_summary={
                        "response": response_payload,
                        "payloadSummary": secret_safe_summary(payload),
                        "originalActionLogId": _action_id_for_record(
                            idempotency.record
                        ),
                    },
                )
                return JsonResponse(response_payload, status=response_status)

            try:
                report = IncidentReport.objects.get(pk=report_id)
            except IncidentReport.DoesNotExist as exc:
                raise _RiskReportNotFound from exc

            result = create_risk_assessment(
                report=report,
                level=normalized["level"],
                score=normalized["score"],
                factors=normalized["factors"],
                source=normalized["source"],
                evaluator_version=normalized["evaluator_version"],
                integration_client=integration_client,
                external_assessment_id=normalized["external_assessment_id"],
            )
            response_payload = _risk_accepted_payload(result)
            action_log = _create_risk_action_log(
                request=request,
                integration_client=integration_client,
                target_type=TARGET_REPORT,
                target_id=target_id,
                payload=payload,
                idempotency_key=idempotency_key,
                external_assessment_id=normalized["external_assessment_id"],
                result_status=IntegrationActionLog.ResultStatus.ACCEPTED,
                result_summary={
                    "response": response_payload,
                    "payloadSummary": secret_safe_summary(payload),
                },
            )
            idempotency.record.response_status_code = 202
            idempotency.record.response_summary = response_payload
            idempotency.record.action_log = action_log
            idempotency.record.save(
                update_fields=(
                    "response_status_code",
                    "response_summary",
                    "action_log",
                    "updated_at",
                )
            )
    except _RiskReportNotFound:
        _create_risk_action_log(
            request=request,
            integration_client=integration_client,
            target_type=TARGET_REPORT,
            target_id=target_id,
            payload=payload,
            idempotency_key=idempotency_key,
            external_assessment_id=normalized["external_assessment_id"],
            result_status=IntegrationActionLog.ResultStatus.REJECTED,
            result_summary={
                "error": {
                    "code": "report_not_found",
                    "message": "Report was not found in the selected tenant.",
                },
                "payloadSummary": secret_safe_summary(payload),
            },
        )
        return _error_response(
            status=404,
            code="report_not_found",
            message="Report was not found in the selected tenant.",
        )
    except IntegrationIdempotencyConflict as exc:
        _create_risk_action_log(
            request=request,
            integration_client=integration_client,
            target_type=TARGET_REPORT,
            target_id=target_id,
            payload=payload,
            idempotency_key=idempotency_key,
            external_assessment_id=normalized["external_assessment_id"],
            result_status=IntegrationActionLog.ResultStatus.REJECTED,
            result_summary={
                "error": {
                    "code": "idempotency_conflict",
                    "message": str(exc),
                },
                "payloadSummary": secret_safe_summary(payload),
            },
        )
        return _error_response(
            status=409,
            code="idempotency_conflict",
            message=str(exc),
        )
    except ValidationError as exc:
        _create_risk_action_log(
            request=request,
            integration_client=integration_client,
            target_type=TARGET_REPORT,
            target_id=target_id,
            payload=payload,
            idempotency_key=idempotency_key,
            external_assessment_id=normalized["external_assessment_id"],
            result_status=IntegrationActionLog.ResultStatus.REJECTED,
            result_summary={
                "error": {
                    "code": "invalid_payload",
                    "message": str(exc),
                },
                "payloadSummary": secret_safe_summary(payload),
            },
        )
        return _error_response(
            status=400,
            code="invalid_payload",
            message=str(exc),
        )
    except Exception:
        _create_risk_action_log(
            request=request,
            integration_client=integration_client,
            target_type=TARGET_REPORT,
            target_id=target_id,
            payload=payload,
            idempotency_key=idempotency_key,
            external_assessment_id=normalized["external_assessment_id"],
            result_status=IntegrationActionLog.ResultStatus.FAILED,
            result_summary={
                "error": {
                    "code": "risk_write_failed",
                    "message": "Risk assessment write failed.",
                },
                "payloadSummary": secret_safe_summary(payload),
            },
        )
        return _error_response(
            status=500,
            code="risk_write_failed",
            message="Risk assessment write failed.",
        )

    return JsonResponse(response_payload, status=202)


def _authorize_ai_image_read_request(
    request,
    *,
    action_type,
    target_type="",
    target_id="",
):
    try:
        assert_integration_tenant_schema()
    except PublicSchemaDenied as exc:
        return (
            _error_response(
                status=403,
                code="tenant_denied",
                message=str(exc),
            ),
            None,
        )

    oauth_context = _verify_oauth_context(request)
    if oauth_context is None:
        return (
            _error_response(
                status=401,
                code="oauth_required",
                message="A valid OAuth2 bearer token is required.",
                headers={"WWW-Authenticate": "Bearer"},
            ),
            None,
        )

    oauth_application = oauth_context["application"]
    oauth_user = oauth_context["user"]
    try:
        auth_context = get_active_integration_client(oauth_application)
    except (PublicSchemaDenied, IntegrationClientDenied) as exc:
        return (
            _error_response(
                status=403,
                code="integration_client_denied",
                message=str(exc),
            ),
            None,
        )

    integration_client = auth_context.integration_client
    if oauth_user is not None:
        _create_ai_image_action_log(
            request=request,
            integration_client=integration_client,
            action_type=action_type,
            target_type=target_type,
            target_id=target_id,
            result_status=IntegrationActionLog.ResultStatus.REJECTED,
            result_summary={
                "error": {
                    "code": "service_identity_denied",
                    "message": (
                        "Integration endpoints require service OAuth tokens "
                        "without a human user."
                    ),
                }
            },
        )
        return (
            _error_response(
                status=403,
                code="service_identity_denied",
                message=(
                    "Integration endpoints require service OAuth tokens without a "
                    "human user."
                ),
            ),
            None,
        )

    if not integration_client.has_scope(IntegrationScope.AI_READ_IMAGES):
        _create_ai_image_action_log(
            request=request,
            integration_client=integration_client,
            action_type=action_type,
            target_type=target_type,
            target_id=target_id,
            result_status=IntegrationActionLog.ResultStatus.REJECTED,
            result_summary={
                "error": {
                    "code": "scope_denied",
                    "message": (
                        "Integration client lacks required scope: "
                        f"{IntegrationScope.AI_READ_IMAGES}"
                    ),
                }
            },
        )
        return (
            _error_response(
                status=403,
                code="scope_denied",
                message=(
                    "Integration client lacks required scope: "
                    f"{IntegrationScope.AI_READ_IMAGES}"
                ),
            ),
            None,
        )

    try:
        assert_integration_feature_enabled(FEATURE_AI)
    except IntegrationPolicyDenied as exc:
        _create_ai_image_action_log(
            request=request,
            integration_client=integration_client,
            action_type=action_type,
            target_type=target_type,
            target_id=target_id,
            result_status=IntegrationActionLog.ResultStatus.REJECTED,
            result_summary={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                }
            },
        )
        return (
            _error_response(status=403, code=exc.code, message=exc.message),
            None,
        )

    return None, integration_client


def _authorize_incident_read_request(request, target_id=""):
    try:
        assert_integration_tenant_schema()
    except PublicSchemaDenied as exc:
        return (
            _error_response(
                status=403,
                code="tenant_denied",
                message=str(exc),
            ),
            None,
        )

    oauth_context = _verify_oauth_context(request)
    if oauth_context is None:
        return (
            _error_response(
                status=401,
                code="oauth_required",
                message="A valid OAuth2 bearer token is required.",
                headers={"WWW-Authenticate": "Bearer"},
            ),
            None,
        )

    oauth_application = oauth_context["application"]
    oauth_user = oauth_context["user"]
    try:
        auth_context = get_active_integration_client(oauth_application)
    except (PublicSchemaDenied, IntegrationClientDenied) as exc:
        return (
            _error_response(
                status=403,
                code="integration_client_denied",
                message=str(exc),
            ),
            None,
        )

    integration_client = auth_context.integration_client
    if oauth_user is not None:
        _create_incident_read_action_log(
            request=request,
            integration_client=integration_client,
            target_id=target_id,
            result_status=IntegrationActionLog.ResultStatus.REJECTED,
            result_summary={
                "error": {
                    "code": "service_identity_denied",
                    "message": (
                        "Integration endpoints require service OAuth tokens "
                        "without a human user."
                    ),
                }
            },
        )
        return (
            _error_response(
                status=403,
                code="service_identity_denied",
                message=(
                    "Integration endpoints require service OAuth tokens without a "
                    "human user."
                ),
            ),
            None,
        )

    if not integration_client.has_scope(IntegrationScope.INCIDENT_READ):
        _create_incident_read_action_log(
            request=request,
            integration_client=integration_client,
            target_id=target_id,
            result_status=IntegrationActionLog.ResultStatus.REJECTED,
            result_summary={
                "error": {
                    "code": "scope_denied",
                    "message": (
                        "Integration client lacks required scope: "
                        f"{IntegrationScope.INCIDENT_READ}"
                    ),
                }
            },
        )
        return (
            _error_response(
                status=403,
                code="scope_denied",
                message=(
                    "Integration client lacks required scope: "
                    f"{IntegrationScope.INCIDENT_READ}"
                ),
            ),
            None,
        )

    try:
        assert_integration_feature_enabled()
    except IntegrationPolicyDenied as exc:
        _create_incident_read_action_log(
            request=request,
            integration_client=integration_client,
            target_id=target_id,
            result_status=IntegrationActionLog.ResultStatus.REJECTED,
            result_summary={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                }
            },
        )
        return (
            _error_response(status=403, code=exc.code, message=exc.message),
            None,
        )

    return None, integration_client


def _authorize_census_read_request(request, target_type="", target_id=""):
    try:
        assert_integration_tenant_schema()
    except PublicSchemaDenied as exc:
        return (
            _error_response(
                status=403,
                code="tenant_denied",
                message=str(exc),
            ),
            None,
        )

    oauth_context = _verify_oauth_context(request)
    if oauth_context is None:
        return (
            _error_response(
                status=401,
                code="oauth_required",
                message="A valid OAuth2 bearer token is required.",
                headers={"WWW-Authenticate": "Bearer"},
            ),
            None,
        )

    oauth_application = oauth_context["application"]
    oauth_user = oauth_context["user"]
    try:
        auth_context = get_active_integration_client(oauth_application)
    except (PublicSchemaDenied, IntegrationClientDenied) as exc:
        return (
            _error_response(
                status=403,
                code="integration_client_denied",
                message=str(exc),
            ),
            None,
        )

    integration_client = auth_context.integration_client
    if oauth_user is not None:
        _create_census_read_action_log(
            request=request,
            integration_client=integration_client,
            target_type=target_type,
            target_id=target_id,
            result_status=IntegrationActionLog.ResultStatus.REJECTED,
            result_summary={
                "error": {
                    "code": "service_identity_denied",
                    "message": (
                        "Integration endpoints require service OAuth tokens "
                        "without a human user."
                    ),
                }
            },
        )
        return (
            _error_response(
                status=403,
                code="service_identity_denied",
                message=(
                    "Integration endpoints require service OAuth tokens without a "
                    "human user."
                ),
            ),
            None,
        )

    if not integration_client.has_scope(IntegrationScope.CENSUS_READ):
        _create_census_read_action_log(
            request=request,
            integration_client=integration_client,
            target_type=target_type,
            target_id=target_id,
            result_status=IntegrationActionLog.ResultStatus.REJECTED,
            result_summary={
                "error": {
                    "code": "scope_denied",
                    "message": (
                        "Integration client lacks required scope: "
                        f"{IntegrationScope.CENSUS_READ}"
                    ),
                }
            },
        )
        return (
            _error_response(
                status=403,
                code="scope_denied",
                message=(
                    "Integration client lacks required scope: "
                    f"{IntegrationScope.CENSUS_READ}"
                ),
            ),
            None,
        )

    try:
        assert_integration_feature_enabled()
    except IntegrationPolicyDenied as exc:
        _create_census_read_action_log(
            request=request,
            integration_client=integration_client,
            target_type=target_type,
            target_id=target_id,
            result_status=IntegrationActionLog.ResultStatus.REJECTED,
            result_summary={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                }
            },
        )
        return (
            _error_response(status=403, code=exc.code, message=exc.message),
            None,
        )

    return None, integration_client


def _authorize_cluster_request(
    request,
    *,
    action_type,
    target_type="",
    target_id="",
):
    try:
        assert_integration_tenant_schema()
    except PublicSchemaDenied as exc:
        return (
            _error_response(
                status=403,
                code="tenant_denied",
                message=str(exc),
            ),
            None,
        )

    oauth_context = _verify_oauth_context(request)
    if oauth_context is None:
        return (
            _error_response(
                status=401,
                code="oauth_required",
                message="A valid OAuth2 bearer token is required.",
                headers={"WWW-Authenticate": "Bearer"},
            ),
            None,
        )

    oauth_application = oauth_context["application"]
    oauth_user = oauth_context["user"]
    try:
        auth_context = get_active_integration_client(oauth_application)
    except (PublicSchemaDenied, IntegrationClientDenied) as exc:
        return (
            _error_response(
                status=403,
                code="integration_client_denied",
                message=str(exc),
            ),
            None,
        )

    integration_client = auth_context.integration_client
    if oauth_user is not None:
        _create_cluster_action_log(
            request=request,
            integration_client=integration_client,
            action_type=action_type,
            target_type=target_type,
            target_id=target_id,
            result_status=IntegrationActionLog.ResultStatus.REJECTED,
            result_summary={
                "error": {
                    "code": "service_identity_denied",
                    "message": (
                        "Integration endpoints require service OAuth tokens "
                        "without a human user."
                    ),
                }
            },
        )
        return (
            _error_response(
                status=403,
                code="service_identity_denied",
                message=(
                    "Integration endpoints require service OAuth tokens without a "
                    "human user."
                ),
            ),
            None,
        )

    if not integration_client.has_scope(IntegrationScope.CLUSTER_WRITE_RESULT):
        _create_cluster_action_log(
            request=request,
            integration_client=integration_client,
            action_type=action_type,
            target_type=target_type,
            target_id=target_id,
            result_status=IntegrationActionLog.ResultStatus.REJECTED,
            result_summary={
                "error": {
                    "code": "scope_denied",
                    "message": (
                        "Integration client lacks required scope: "
                        f"{IntegrationScope.CLUSTER_WRITE_RESULT}"
                    ),
                }
            },
        )
        return (
            _error_response(
                status=403,
                code="scope_denied",
                message=(
                    "Integration client lacks required scope: "
                    f"{IntegrationScope.CLUSTER_WRITE_RESULT}"
                ),
            ),
            None,
        )

    try:
        assert_integration_feature_enabled(FEATURE_CLUSTER_DETECTOR)
    except IntegrationPolicyDenied as exc:
        _create_cluster_action_log(
            request=request,
            integration_client=integration_client,
            action_type=action_type,
            target_type=target_type,
            target_id=target_id,
            result_status=IntegrationActionLog.ResultStatus.REJECTED,
            result_summary={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                }
            },
        )
        return (
            _error_response(status=403, code=exc.code, message=exc.message),
            None,
        )

    return None, integration_client


def _normalize_census_query(query_params, *, allowed_keys, include_window):
    unknown_keys = sorted(set(query_params.keys()) - allowed_keys)
    if unknown_keys:
        raise _CensusFilterError(f"Unsupported query parameters: {unknown_keys}")

    village_id = _parse_census_positive_int(
        _single_query_value(query_params, "villageId", required=True),
        "villageId",
    )
    try:
        village = Village.objects.select_related("authority").get(pk=village_id)
    except Village.DoesNotExist as exc:
        raise _CensusFilterError(
            "villageId was not found in the selected tenant."
        ) from exc

    kind = _parse_census_kind(
        _single_query_value(query_params, "kind", required=True)
    )
    filters = {
        "village": village,
        "kind": kind,
        "from_date": None,
        "to_date": None,
        "from": None,
        "to": None,
        "limit": CENSUS_LIST_DEFAULT_LIMIT,
        "offset": 0,
    }
    if not include_window:
        return filters

    from_date = _parse_census_date(
        _single_query_value(query_params, "from"),
        "from",
    )
    to_date = _parse_census_date(
        _single_query_value(query_params, "to"),
        "to",
    )
    if from_date and to_date and from_date > to_date:
        raise _CensusFilterError("from must be on or before to.")

    limit = _parse_census_positive_int(
        _single_query_value(query_params, "limit"),
        "limit",
        default=CENSUS_LIST_DEFAULT_LIMIT,
    )
    if limit > CENSUS_LIST_MAX_LIMIT:
        limit = CENSUS_LIST_MAX_LIMIT

    offset = _parse_census_non_negative_int(
        _single_query_value(query_params, "offset"),
        "offset",
        default=0,
    )
    if offset > CENSUS_LIST_MAX_OFFSET:
        raise _CensusFilterError(f"offset must be {CENSUS_LIST_MAX_OFFSET} or lower.")

    filters.update(
        {
            "from_date": from_date,
            "to_date": to_date,
            "from": from_date.isoformat() if from_date else None,
            "to": to_date.isoformat() if to_date else None,
            "limit": limit,
            "offset": offset,
        }
    )
    return filters


def _single_query_value(query_params, key, required=False):
    if key not in query_params:
        if required:
            raise _CensusFilterError(f"{key} is required.")
        return None

    values = query_params.getlist(key)
    if len(values) != 1:
        raise _CensusFilterError(f"{key} must be supplied once.")
    value = values[0]
    if value is None or str(value).strip() == "":
        raise _CensusFilterError(f"{key} must not be empty.")
    return str(value).strip()


def _parse_census_positive_int(raw_value, field_name, default=None):
    if raw_value is None:
        return default

    try:
        value = int(raw_value)
    except (TypeError, ValueError) as exc:
        raise _CensusFilterError(f"{field_name} must be an integer.") from exc

    if value < 1:
        raise _CensusFilterError(f"{field_name} must be greater than zero.")

    return value


def _parse_census_non_negative_int(raw_value, field_name, default=None):
    if raw_value is None:
        return default

    try:
        value = int(raw_value)
    except (TypeError, ValueError) as exc:
        raise _CensusFilterError(f"{field_name} must be an integer.") from exc

    if value < 0:
        raise _CensusFilterError(f"{field_name} must be zero or greater.")

    return value


def _parse_census_kind(raw_value):
    if raw_value not in (CensusDefinition.Kind.ANIMAL, CensusDefinition.Kind.HUMAN):
        raise _CensusFilterError("kind must be ANIMAL or HUMAN.")
    return raw_value


def _parse_census_date(raw_value, field_name):
    if raw_value is None:
        return None

    try:
        parsed = date.fromisoformat(raw_value)
    except ValueError as exc:
        raise _CensusFilterError(f"{field_name} must be an ISO date.") from exc

    if parsed.isoformat() != raw_value:
        raise _CensusFilterError(f"{field_name} must be an ISO date.")

    return parsed


def _census_snapshot_queryset(filters):
    queryset = (
        VillageCensusSnapshot.objects.select_related(
            "village",
            "village__authority",
            "definition_version",
            "definition_version__definition",
        )
        .prefetch_related("facts", "human_facts")
        .filter(
            village=filters["village"],
            definition_version__definition__kind=filters["kind"],
        )
        .order_by("-census_date", "-submitted_at", "-created_at", "-id")
    )

    if filters["from_date"]:
        queryset = queryset.filter(census_date__gte=filters["from_date"])
    if filters["to_date"]:
        queryset = queryset.filter(census_date__lte=filters["to_date"])

    return queryset


def _normalize_cluster_list_filters(query_params):
    unknown_keys = sorted(set(query_params.keys()) - CLUSTER_LIST_ALLOWED_QUERY_KEYS)
    if unknown_keys:
        raise _ClusterFilterError(f"Unsupported query parameters: {unknown_keys}")

    external_cluster_id = _cluster_single_query_value(
        query_params,
        "externalClusterId",
    )
    if external_cluster_id and len(external_cluster_id) > 200:
        raise _ClusterFilterError(
            "externalClusterId must be 200 characters or fewer."
        )

    from_date = _parse_cluster_date(
        _cluster_single_query_value(query_params, "from"),
        "from",
    )
    to_date = _parse_cluster_date(
        _cluster_single_query_value(query_params, "to"),
        "to",
    )
    if from_date and to_date and from_date > to_date:
        raise _ClusterFilterError("from must be on or before to.")

    authority_id = _parse_cluster_positive_int(
        _cluster_single_query_value(query_params, "authorityId"),
        "authorityId",
    )
    if authority_id is not None and not Authority.objects.filter(pk=authority_id).exists():
        raise _ClusterFilterError("authorityId was not found in the selected tenant.")

    village_id = _parse_cluster_positive_int(
        _cluster_single_query_value(query_params, "villageId"),
        "villageId",
    )
    if village_id is not None and not Village.objects.filter(pk=village_id).exists():
        raise _ClusterFilterError("villageId was not found in the selected tenant.")

    risk_level = _cluster_single_query_value(query_params, "riskLevel")
    if risk_level is not None and risk_level not in RiskAssessment.Level.values:
        raise _ClusterFilterError(
            "riskLevel must be one of LOW, MEDIUM, HIGH, CRITICAL."
        )

    limit = _parse_cluster_positive_int(
        _cluster_single_query_value(query_params, "limit"),
        "limit",
        default=CLUSTER_LIST_DEFAULT_LIMIT,
    )
    if limit > CLUSTER_LIST_MAX_LIMIT:
        limit = CLUSTER_LIST_MAX_LIMIT

    offset = _parse_cluster_non_negative_int(
        _cluster_single_query_value(query_params, "offset"),
        "offset",
        default=0,
    )
    if offset > CLUSTER_LIST_MAX_OFFSET:
        raise _ClusterFilterError(
            f"offset must be {CLUSTER_LIST_MAX_OFFSET} or lower."
        )

    return {
        "external_cluster_id": external_cluster_id,
        "from_date": from_date,
        "to_date": to_date,
        "from": from_date.isoformat() if from_date else None,
        "to": to_date.isoformat() if to_date else None,
        "authority_id": authority_id,
        "village_id": village_id,
        "risk_level": risk_level,
        "limit": limit,
        "offset": offset,
    }


def _cluster_queryset_for_filters(filters, *, integration_client):
    queryset = IntegrationClusterResult.objects.select_related(
        "integration_client"
    ).filter(
        integration_client=integration_client
    ).order_by("-window_start", "-window_end", "-created_at", "-cluster_id")

    if filters["external_cluster_id"]:
        queryset = queryset.filter(external_cluster_id=filters["external_cluster_id"])
    if filters["from_date"]:
        queryset = queryset.filter(window_end__gte=filters["from_date"])
    if filters["to_date"]:
        queryset = queryset.filter(window_start__lte=filters["to_date"])
    if filters["authority_id"] is not None:
        queryset = queryset.filter(authority_ids__contains=[filters["authority_id"]])
    if filters["village_id"] is not None:
        queryset = queryset.filter(village_ids__contains=[filters["village_id"]])
    if filters["risk_level"]:
        queryset = queryset.filter(risk_level=filters["risk_level"])

    return queryset


def _is_cluster_external_unique_conflict(exc):
    return "unique_active_integration_cluster_external" in str(exc)


def _cluster_single_query_value(query_params, key, required=False):
    if key not in query_params:
        if required:
            raise _ClusterFilterError(f"{key} is required.")
        return None

    values = query_params.getlist(key)
    if len(values) != 1:
        raise _ClusterFilterError(f"{key} must be supplied once.")
    value = values[0]
    if value is None or str(value).strip() == "":
        raise _ClusterFilterError(f"{key} must not be empty.")
    return str(value).strip()


def _parse_cluster_positive_int(raw_value, field_name, default=None):
    if raw_value is None:
        return default

    try:
        value = int(raw_value)
    except (TypeError, ValueError) as exc:
        raise _ClusterFilterError(f"{field_name} must be an integer.") from exc

    if value < 1:
        raise _ClusterFilterError(f"{field_name} must be greater than zero.")

    return value


def _parse_cluster_non_negative_int(raw_value, field_name, default=None):
    if raw_value is None:
        return default

    try:
        value = int(raw_value)
    except (TypeError, ValueError) as exc:
        raise _ClusterFilterError(f"{field_name} must be an integer.") from exc

    if value < 0:
        raise _ClusterFilterError(f"{field_name} must be zero or greater.")

    return value


def _parse_cluster_date(raw_value, field_name):
    if raw_value is None:
        return None

    try:
        parsed = date.fromisoformat(raw_value)
    except ValueError as exc:
        raise _ClusterFilterError(f"{field_name} must be an ISO date.") from exc

    if parsed.isoformat() != raw_value:
        raise _ClusterFilterError(f"{field_name} must be an ISO date.")

    return parsed


def _normalize_incident_list_filters(query_params):
    unknown_keys = sorted(set(query_params.keys()) - INCIDENT_LIST_ALLOWED_QUERY_KEYS)
    if unknown_keys:
        raise _IncidentFilterError(f"Unsupported query parameters: {unknown_keys}")

    if "villageId" in query_params:
        raise _IncidentFilterError(
            "villageId filter is not supported because incidents have no safe "
            "direct village relation.",
            code="invalid_filter",
        )

    from_date = _parse_filter_date(query_params.get("from"), "from")
    to_date = _parse_filter_date(query_params.get("to"), "to")
    if from_date and to_date and from_date > to_date:
        raise _IncidentFilterError("from must be on or before to.")

    limit = _parse_positive_int(
        query_params.get("limit"),
        "limit",
        default=INCIDENT_LIST_DEFAULT_LIMIT,
    )
    if limit > INCIDENT_LIST_MAX_LIMIT:
        limit = INCIDENT_LIST_MAX_LIMIT

    offset = _parse_non_negative_int(
        query_params.get("offset"),
        "offset",
        default=0,
    )
    if offset > INCIDENT_LIST_MAX_OFFSET:
        raise _IncidentFilterError(
            f"offset must be {INCIDENT_LIST_MAX_OFFSET} or lower."
        )

    authority_id = None
    if "authorityId" in query_params:
        authority_id = _parse_positive_int(query_params.get("authorityId"), "authorityId")

    include_child_authorities = _parse_optional_bool(
        query_params.get("includeChildAuthorities"),
        "includeChildAuthorities",
        default=False,
    )
    if include_child_authorities and authority_id is None:
        raise _IncidentFilterError("includeChildAuthorities requires authorityId.")

    report_type_ids = _parse_report_type_ids(query_params.get("reportTypeIds"))
    test_flag = _parse_optional_bool(query_params.get("testFlag"), "testFlag")

    return {
        "from_date": from_date,
        "to_date": to_date,
        "from": from_date.isoformat() if from_date else None,
        "to": to_date.isoformat() if to_date else None,
        "limit": limit,
        "offset": offset,
        "authority_id": authority_id,
        "include_child_authorities": include_child_authorities,
        "report_type_ids": report_type_ids,
        "test_flag": test_flag,
    }


def _incident_queryset_for_filters(filters):
    queryset = (
        IncidentReport.objects.select_related("report_type", "report_type__category")
        .prefetch_related("relevant_authorities")
        .order_by("-incident_date", "-created_at", "-id")
    )

    if filters["from_date"]:
        queryset = queryset.filter(incident_date__gte=filters["from_date"])
    if filters["to_date"]:
        queryset = queryset.filter(incident_date__lte=filters["to_date"])

    if filters["authority_id"] is not None:
        try:
            authority = Authority.objects.get(pk=filters["authority_id"])
        except Authority.DoesNotExist as exc:
            raise _IncidentFilterError(
                "authorityId was not found in the selected tenant."
            ) from exc

        authority_ids = [authority.id]
        if filters["include_child_authorities"]:
            authority_ids = [
                child.id for child in authority.all_inherits_down()
            ]
        queryset = queryset.filter(relevant_authorities__id__in=authority_ids).distinct()

    if filters["report_type_ids"]:
        queryset = queryset.filter(report_type_id__in=filters["report_type_ids"])

    if filters["test_flag"] is not None:
        queryset = queryset.filter(test_flag=filters["test_flag"])

    return queryset


def _parse_filter_date(raw_value, field_name):
    if raw_value is None:
        return None
    if raw_value == "":
        raise _IncidentFilterError(f"{field_name} must be an ISO date.")

    try:
        return date.fromisoformat(raw_value)
    except ValueError as exc:
        raise _IncidentFilterError(f"{field_name} must be an ISO date.") from exc


def _parse_positive_int(raw_value, field_name, default=None):
    if raw_value is None:
        return default
    if raw_value == "":
        raise _IncidentFilterError(f"{field_name} must be an integer.")

    try:
        value = int(raw_value)
    except (TypeError, ValueError) as exc:
        raise _IncidentFilterError(f"{field_name} must be an integer.") from exc

    if value < 1:
        raise _IncidentFilterError(f"{field_name} must be greater than zero.")

    return value


def _parse_non_negative_int(raw_value, field_name, default=None):
    if raw_value is None:
        return default
    if raw_value == "":
        raise _IncidentFilterError(f"{field_name} must be an integer.")

    try:
        value = int(raw_value)
    except (TypeError, ValueError) as exc:
        raise _IncidentFilterError(f"{field_name} must be an integer.") from exc

    if value < 0:
        raise _IncidentFilterError(f"{field_name} must be zero or greater.")

    return value


def _parse_optional_bool(raw_value, field_name, default=None):
    if raw_value is None:
        return default
    if raw_value == "":
        raise _IncidentFilterError(f"{field_name} must be true or false.")

    normalized = str(raw_value).strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False

    raise _IncidentFilterError(f"{field_name} must be true or false.")


def _parse_report_type_ids(raw_value):
    if raw_value is None:
        return []
    if raw_value == "":
        raise _IncidentFilterError("reportTypeIds must be comma-separated UUIDs.")

    values = [value.strip() for value in raw_value.split(",")]
    if not values or any(not value for value in values):
        raise _IncidentFilterError("reportTypeIds must be comma-separated UUIDs.")

    try:
        return [uuid.UUID(value) for value in values]
    except ValueError as exc:
        raise _IncidentFilterError("reportTypeIds must be comma-separated UUIDs.") from exc


def _incident_payload(report, *, current_risk_assessment=None, include_links=False):
    report_type = report.report_type
    payload = {
        "id": str(report.id),
        "createdAt": _isoformat_or_none(report.created_at),
        "updatedAt": _isoformat_or_none(report.updated_at),
        "incidentDate": report.incident_date.isoformat()
        if report.incident_date
        else None,
        "testFlag": report.test_flag,
        "reportType": {
            "id": str(report_type.id),
            "name": report_type.name,
            "category": str(report_type.category)
            if report_type.category_id
            else None,
        },
        "relevantAuthorityIds": sorted(
            authority.id for authority in report.relevant_authorities.all()
        ),
        "caseId": str(report.case_id) if report.case_id else None,
        "location": _location_payload(report),
        "currentRiskAssessment": _risk_assessment_payload(current_risk_assessment),
    }
    if include_links:
        payload["links"] = _incident_links(report.id)
    return payload


def _village_payload(village):
    return {
        "id": village.id,
        "code": village.code,
        "name": village.name,
        "authorityId": village.authority_id,
    }


def _census_snapshot_payload(snapshot, kind):
    return {
        "id": snapshot.id,
        "censusDate": snapshot.census_date.isoformat(),
        "submittedAt": snapshot.submitted_at.isoformat()
        if snapshot.submitted_at
        else None,
        "status": snapshot.status,
        "definitionVersion": _census_definition_version_payload(
            snapshot.definition_version
        ),
        "facts": _census_fact_payloads(snapshot, kind),
    }


def _census_definition_version_payload(definition_version):
    if definition_version is None:
        return None

    return {
        "id": definition_version.id,
        "version": definition_version.version,
        "kind": definition_version.definition.kind,
    }


def _census_fact_payloads(snapshot, kind):
    if kind == CensusDefinition.Kind.ANIMAL:
        return [
            {
                "rowKey": fact.row_key,
                "rowLabel": fact.row_label,
                "extraDimensions": fact.extra_dimensions,
                "measures": fact.measures,
            }
            for fact in snapshot.facts.all()
        ]
    if kind == CensusDefinition.Kind.HUMAN:
        return [
            {
                "rowKey": fact.row_key,
                "dimensions": fact.dimensions,
                "measures": fact.measures,
            }
            for fact in snapshot.human_facts.all()
        ]
    return []


def _current_risk_assessments_by_report_id(report_ids):
    report_id_values = [str(report_id) for report_id in report_ids]
    if not report_id_values:
        return {}

    return {
        str(assessment.report_id): assessment
        for assessment in RiskAssessment.objects.filter(
            report_id__in=report_id_values,
            is_current=True,
        )
    }


def _location_payload(report):
    if report.gps_location is None:
        return None

    return {
        "lon": float(report.gps_location.x),
        "lat": float(report.gps_location.y),
    }


def _risk_assessment_payload(assessment):
    if assessment is None:
        return None

    return {
        "level": assessment.level,
        "score": _score_for_response(assessment.score),
        "source": assessment.source,
        "evaluatorVersion": assessment.evaluator_version,
        "externalAssessmentId": assessment.external_assessment_id,
        "createdAt": assessment.created_at.isoformat(),
    }


def _incident_links(report_id):
    return {
        "comments": f"/api/integrations/v1/reports/{report_id}/comments",
        "riskAssessments": f"/api/integrations/v1/reports/{report_id}/risk-assessments",
        "images": f"/api/integrations/v1/reports/{report_id}/images",
    }


def _ordered_report_images(report):
    images = list(report.images.all())
    cover_id = report.cover_image_id
    images.sort(
        key=lambda image: (
            0 if cover_id and image.id == cover_id else 1,
            image.created_at or image.id,
            str(image.id),
        )
    )
    return images


def _image_metadata_payload(image, *, report):
    return {
        "id": str(image.id),
        "isCover": bool(report.cover_image_id and image.id == report.cover_image_id),
        "contentType": _image_content_type(image),
        "byteSize": _image_byte_size(image),
        "createdAt": _isoformat_or_none(image.created_at),
        "links": {
            "content": (
                f"/api/integrations/v1/reports/{report.id}/images/{image.id}/content"
            ),
        },
    }


_GENERIC_CONTENT_TYPES = frozenset(
    {
        "",
        "application/octet-stream",
        "binary/octet-stream",
        "application/binary",
    }
)


def _image_content_type(image):
    """Resolve a useful MIME type for report images.

    Prefer an explicit storage/upload content type, then filename extension,
    then a small magic-byte sniff. Extensionless UUID storage names (common
    with S3/MinIO) often only resolve correctly via sniffing.
    """
    file_field = image.file
    content_type = getattr(getattr(file_field, "file", None), "content_type", None)
    if content_type and content_type.lower().split(";", 1)[0].strip() not in _GENERIC_CONTENT_TYPES:
        return content_type.split(";", 1)[0].strip()

    guessed, _encoding = mimetypes.guess_type(getattr(file_field, "name", "") or "")
    if guessed and guessed.lower() not in _GENERIC_CONTENT_TYPES:
        return guessed

    sniffed = _sniff_image_content_type(file_field)
    if sniffed:
        return sniffed

    return "application/octet-stream"


def _sniff_image_content_type(file_field):
    if not file_field or not getattr(file_field, "name", None):
        return None
    # Open via storage so we do not mutate/close the FieldFile handle that
    # FileResponse may already be streaming from.
    try:
        storage = getattr(file_field, "storage", None)
        if storage is not None:
            with storage.open(file_field.name, "rb") as handle:
                head = handle.read(32) or b""
        else:
            with file_field.open("rb") as handle:
                head = handle.read(32) or b""
    except Exception:
        return None

    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if len(head) >= 12 and head.startswith(b"RIFF") and head[8:12] == b"WEBP":
        return "image/webp"
    return None


def _image_byte_size(image):
    try:
        size = image.file.size
    except Exception:
        return None
    if size is None:
        return None
    return int(size)


def _isoformat_or_none(value):
    if value is None:
        return None
    return value.isoformat()


def _verify_oauth_context(request):
    validator = OAuth2Validator()
    core = OAuthLibCore(Server(validator))
    valid, oauth_request = core.verify_request(request, scopes=[])
    if not valid:
        return None
    return {
        "application": getattr(oauth_request, "client", None),
        "user": getattr(oauth_request, "user", None),
    }


def _parse_json_body(request):
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, "Request body must be valid JSON."

    if not isinstance(payload, dict):
        return None, "Request body must be a JSON object."

    return payload, None


def _normalize_comment_payload(payload):
    if payload is None:
        return _empty_normalized_payload(), "Request body must be a JSON object."

    unknown_keys = sorted(set(payload.keys()) - ALLOWED_COMMENT_PAYLOAD_KEYS)
    if unknown_keys:
        return (
            _empty_normalized_payload(),
            f"Unsupported payload fields: {unknown_keys}",
        )

    external_action_id = ""
    if "externalActionId" in payload:
        external_action_id = payload.get("externalActionId")
        if not isinstance(external_action_id, str):
            return _empty_normalized_payload(), "externalActionId must be a string."
    if len(external_action_id) > 200:
        return (
            _empty_normalized_payload(),
            "externalActionId must be 200 characters or fewer.",
        )

    body = payload.get("body")
    comment = payload.get("comment")
    if body is not None and comment is not None and body != comment:
        return (
            _empty_normalized_payload(),
            "body and comment must match when both are supplied.",
        )
    if body is None:
        body = comment
    if not isinstance(body, str) or not body.strip():
        return _empty_normalized_payload(), "body must be a non-empty string."

    visibility = payload.get("visibility", IntegrationReportComment.Visibility.STAFF)
    if visibility != IntegrationReportComment.Visibility.STAFF:
        return (
            _empty_normalized_payload(),
            "visibility currently supports only staff.",
        )

    metadata = payload.get("metadata", {})
    if metadata is None:
        metadata = {}
    if not isinstance(metadata, dict):
        return _empty_normalized_payload(), "metadata must be an object."

    recommendation = payload.get("recommendation", {})
    if recommendation is None:
        recommendation = {}
    if not isinstance(recommendation, dict):
        return _empty_normalized_payload(), "recommendation must be an object."

    return (
        {
            "body": body.strip(),
            "visibility": visibility,
            "external_action_id": external_action_id.strip(),
            "metadata": metadata,
            "recommendation": recommendation,
        },
        None,
    )


def _empty_normalized_payload():
    return {
        "body": "",
        "visibility": IntegrationReportComment.Visibility.STAFF,
        "external_action_id": "",
        "metadata": {},
        "recommendation": {},
    }


def _normalize_risk_payload(payload):
    if payload is None:
        return _empty_normalized_risk_payload(), "Request body must be a JSON object."

    unknown_keys = sorted(set(payload.keys()) - ALLOWED_RISK_PAYLOAD_KEYS)
    if unknown_keys:
        return (
            _empty_normalized_risk_payload(),
            f"Unsupported payload fields: {unknown_keys}",
        )

    external_assessment_id = ""
    if "externalAssessmentId" in payload:
        external_assessment_id = payload.get("externalAssessmentId")
        if not isinstance(external_assessment_id, str):
            return (
                _empty_normalized_risk_payload(),
                "externalAssessmentId must be a string.",
            )
    if len(external_assessment_id) > 200:
        return (
            _empty_normalized_risk_payload(),
            "externalAssessmentId must be 200 characters or fewer.",
        )

    level = payload.get("level")
    if level not in RiskAssessment.Level.values:
        return (
            _empty_normalized_risk_payload(),
            "level must be one of LOW, MEDIUM, HIGH, CRITICAL.",
        )

    score, score_error = _normalize_score(payload)
    if score_error:
        return _empty_normalized_risk_payload(), score_error

    factors = payload.get("factors", [])
    if not isinstance(factors, (dict, list)):
        return _empty_normalized_risk_payload(), "factors must be an object or array."

    evaluator_version = payload.get("evaluatorVersion", "")
    if evaluator_version is None:
        evaluator_version = ""
    if not isinstance(evaluator_version, str):
        return _empty_normalized_risk_payload(), "evaluatorVersion must be a string."
    if len(evaluator_version) > 120:
        return (
            _empty_normalized_risk_payload(),
            "evaluatorVersion must be 120 characters or fewer.",
        )

    source = payload.get(
        "source",
        RiskAssessment.Source.EXTERNAL_RISK_EVALUATOR,
    )
    if not isinstance(source, str):
        return (
            _empty_normalized_risk_payload(),
            "source must be external_risk_evaluator or ai.",
        )
    if source not in INTEGRATION_RISK_SOURCES:
        return (
            _empty_normalized_risk_payload(),
            "source must be external_risk_evaluator or ai.",
        )

    return (
        {
            "external_assessment_id": external_assessment_id.strip(),
            "level": level,
            "score": score,
            "factors": factors,
            "evaluator_version": evaluator_version.strip(),
            "source": source,
        },
        None,
    )


def _normalize_score(payload):
    if "score" not in payload or payload.get("score") is None:
        return None, None

    score_value = payload.get("score")
    if isinstance(score_value, bool) or not isinstance(score_value, (int, float)):
        return None, "score must be a number between 0 and 1."

    try:
        score = Decimal(str(score_value))
    except (InvalidOperation, ValueError):
        return None, "score must be a number between 0 and 1."

    if not score.is_finite() or score < Decimal("0") or score > Decimal("1"):
        return None, "score must be a number between 0 and 1."

    return score, None


def _empty_normalized_risk_payload():
    return {
        "external_assessment_id": "",
        "level": "",
        "score": None,
        "factors": [],
        "evaluator_version": "",
        "source": RiskAssessment.Source.EXTERNAL_RISK_EVALUATOR,
    }


def _normalize_cluster_payload(payload):
    empty_payload = _empty_normalized_cluster_payload()
    if payload is None:
        return empty_payload, "Request body must be a JSON object."

    unknown_keys = sorted(set(payload.keys()) - ALLOWED_CLUSTER_PAYLOAD_KEYS)
    if unknown_keys:
        return empty_payload, f"Unsupported payload fields: {unknown_keys}"

    external_cluster_id, error = _normalize_required_cluster_string(
        payload,
        "externalClusterId",
        max_length=200,
    )
    if error:
        return empty_payload, error

    algorithm_version, error = _normalize_required_cluster_string(
        payload,
        "algorithmVersion",
        max_length=120,
    )
    if error:
        return empty_payload, error

    window, error = _normalize_cluster_window(payload.get("window"))
    if error:
        return empty_payload, error

    incident_ids, error = _normalize_cluster_uuid_list(payload, "incidentIds")
    if error:
        return empty_payload, error

    authority_ids, error = _normalize_cluster_int_list(payload, "authorityIds")
    if error:
        return empty_payload, error

    village_ids, error = _normalize_cluster_int_list(payload, "villageIds")
    if error:
        return empty_payload, error

    error = _validate_cluster_targets(
        incident_ids=incident_ids,
        authority_ids=authority_ids,
        village_ids=village_ids,
    )
    if error:
        return empty_payload, error

    geometry = payload.get("geometry")
    if "geometry" in payload and not isinstance(geometry, dict):
        return empty_payload, "geometry must be an object."

    radius_meters, error = _normalize_cluster_decimal(
        payload,
        "radiusMeters",
        min_value=Decimal("0"),
    )
    if error:
        return empty_payload, error

    score, error = _normalize_cluster_decimal(
        payload,
        "score",
        min_value=Decimal("0"),
        max_value=Decimal("1"),
    )
    if error:
        return empty_payload, error

    risk_level = ""
    if "riskLevel" in payload:
        risk_level = payload.get("riskLevel")
        if risk_level not in RiskAssessment.Level.values:
            return (
                empty_payload,
                "riskLevel must be one of LOW, MEDIUM, HIGH, CRITICAL.",
            )

    explanation = payload.get("explanation", "")
    if explanation is None:
        return empty_payload, "explanation must be a string."
    if not isinstance(explanation, str):
        return empty_payload, "explanation must be a string."
    explanation = explanation.strip()
    if "explanation" in payload and not explanation:
        return empty_payload, "explanation must not be empty when supplied."

    metadata = payload.get("metadata", {})
    if metadata is None or not isinstance(metadata, dict):
        return empty_payload, "metadata must be an object."

    return (
        {
            "external_cluster_id": external_cluster_id,
            "algorithm_version": algorithm_version,
            "window_start": window["from"],
            "window_end": window["to"],
            "incident_ids": incident_ids,
            "authority_ids": authority_ids,
            "village_ids": village_ids,
            "geometry": geometry if "geometry" in payload else None,
            "radius_meters": radius_meters,
            "score": score,
            "risk_level": risk_level,
            "explanation": explanation,
            "metadata": secret_safe_summary(
                metadata,
                max_string_length=None,
                max_list_length=None,
            ),
        },
        None,
    )


def _normalize_required_cluster_string(payload, key, *, max_length):
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        return "", f"{key} must be a non-empty string."
    normalized = value.strip()
    if len(normalized) > max_length:
        return "", f"{key} must be {max_length} characters or fewer."
    return normalized, None


def _normalize_cluster_window(raw_window):
    if not isinstance(raw_window, dict):
        return {}, "window must be an object with from and to dates."

    unknown_keys = sorted(set(raw_window.keys()) - ALLOWED_CLUSTER_WINDOW_KEYS)
    if unknown_keys:
        return {}, f"Unsupported window fields: {unknown_keys}"

    from_date, error = _normalize_cluster_payload_date(raw_window.get("from"), "window.from")
    if error:
        return {}, error
    to_date, error = _normalize_cluster_payload_date(raw_window.get("to"), "window.to")
    if error:
        return {}, error
    if from_date > to_date:
        return {}, "window.from must be on or before window.to."

    return {"from": from_date, "to": to_date}, None


def _normalize_cluster_payload_date(raw_value, field_name):
    if not isinstance(raw_value, str) or not raw_value.strip():
        return None, f"{field_name} must be an ISO date."
    raw_value = raw_value.strip()
    try:
        parsed = date.fromisoformat(raw_value)
    except ValueError:
        return None, f"{field_name} must be an ISO date."
    if parsed.isoformat() != raw_value:
        return None, f"{field_name} must be an ISO date."
    return parsed, None


def _normalize_cluster_uuid_list(payload, key):
    if key not in payload:
        return [], None

    raw_values = payload.get(key)
    if not isinstance(raw_values, list):
        return [], f"{key} must be a list of UUID strings."

    values = []
    seen = set()
    for raw_value in raw_values:
        if not isinstance(raw_value, str) or not raw_value.strip():
            return [], f"{key} must contain only UUID strings."
        try:
            value = str(uuid.UUID(raw_value.strip()))
        except ValueError:
            return [], f"{key} must contain only UUID strings."
        if value in seen:
            return [], f"{key} must not contain duplicate values."
        seen.add(value)
        values.append(value)

    return values, None


def _normalize_cluster_int_list(payload, key):
    if key not in payload:
        return [], None

    raw_values = payload.get(key)
    if not isinstance(raw_values, list):
        return [], f"{key} must be a list of integers."

    values = []
    seen = set()
    for raw_value in raw_values:
        if isinstance(raw_value, bool) or not isinstance(raw_value, int):
            return [], f"{key} must contain only integers."
        if raw_value < 1:
            return [], f"{key} must contain only positive integers."
        if raw_value in seen:
            return [], f"{key} must not contain duplicate values."
        seen.add(raw_value)
        values.append(raw_value)

    return values, None


def _validate_cluster_targets(*, incident_ids, authority_ids, village_ids):
    if incident_ids:
        existing_incident_ids = {
            str(incident_id)
            for incident_id in IncidentReport.objects.filter(
                pk__in=incident_ids
            ).values_list("id", flat=True)
        }
        missing_incident_ids = sorted(set(incident_ids) - existing_incident_ids)
        if missing_incident_ids:
            return f"incidentIds were not found: {missing_incident_ids}"

    if authority_ids:
        existing_authority_ids = set(
            Authority.objects.filter(pk__in=authority_ids).values_list("id", flat=True)
        )
        missing_authority_ids = sorted(set(authority_ids) - existing_authority_ids)
        if missing_authority_ids:
            return f"authorityIds were not found: {missing_authority_ids}"

    if village_ids:
        existing_village_ids = set(
            Village.objects.filter(pk__in=village_ids).values_list("id", flat=True)
        )
        missing_village_ids = sorted(set(village_ids) - existing_village_ids)
        if missing_village_ids:
            return f"villageIds were not found: {missing_village_ids}"

    return None


def _normalize_cluster_decimal(payload, key, *, min_value=None, max_value=None):
    if key not in payload:
        return None, None

    raw_value = payload.get(key)
    if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float)):
        return None, f"{key} must be a number."

    try:
        value = Decimal(str(raw_value))
    except (InvalidOperation, ValueError):
        return None, f"{key} must be a number."

    if not value.is_finite():
        return None, f"{key} must be a number."
    if min_value is not None and value < min_value:
        return None, f"{key} must be {min_value} or greater."
    if max_value is not None and value > max_value:
        return None, f"{key} must be {max_value} or lower."

    return value, None


def _empty_normalized_cluster_payload():
    return {
        "external_cluster_id": "",
        "algorithm_version": "",
        "window_start": None,
        "window_end": None,
        "incident_ids": [],
        "authority_ids": [],
        "village_ids": [],
        "geometry": None,
        "radius_meters": None,
        "score": None,
        "risk_level": "",
        "explanation": "",
        "metadata": {},
    }


def _idempotency_key(request, normalized):
    header_key = request.headers.get("Idempotency-Key", "").strip()
    return header_key or normalized.get("external_action_id", "").strip()


def _risk_idempotency_key(request, normalized):
    header_key = request.headers.get("Idempotency-Key", "").strip()
    return header_key or normalized.get("external_assessment_id", "").strip()


def _cluster_idempotency_key(request, normalized):
    header_key = request.headers.get("Idempotency-Key", "").strip()
    return header_key or normalized.get("external_cluster_id", "").strip()


def _accepted_payload(comment):
    return {
        "schemaVersion": SCHEMA_VERSION,
        "status": "accepted",
        "comment": {
            "id": str(comment.comment_id),
            "reportId": str(comment.report_id),
            "visibility": comment.visibility,
            "externalActionId": comment.external_action_id,
            "createdAt": comment.created_at.isoformat(),
        },
        "recommendationStored": bool(comment.recommendation),
    }


def _risk_accepted_payload(result):
    assessment = result.assessment
    return {
        "schemaVersion": SCHEMA_VERSION,
        "status": "accepted",
        "riskAssessment": {
            "id": str(assessment.id),
            "target": {
                "type": "report",
                "id": str(assessment.report_id),
            },
            "level": assessment.level,
            "score": _score_for_response(assessment.score),
            "isCurrent": assessment.is_current,
            "externalAssessmentId": assessment.external_assessment_id,
            "createdAt": assessment.created_at.isoformat(),
            "replacedCurrentCount": result.replaced_current_count,
        },
    }


def _cluster_write_payload(cluster):
    return {
        "schemaVersion": SCHEMA_VERSION,
        "status": "accepted",
        "cluster": _cluster_payload(cluster),
    }


def _cluster_payload(cluster):
    return {
        "id": str(cluster.cluster_id),
        "externalClusterId": cluster.external_cluster_id,
        "algorithmVersion": cluster.algorithm_version,
        "window": {
            "from": cluster.window_start.isoformat(),
            "to": cluster.window_end.isoformat(),
        },
        "incidentIds": cluster.incident_ids,
        "authorityIds": cluster.authority_ids,
        "villageIds": cluster.village_ids,
        "geometry": cluster.geometry,
        "radiusMeters": _decimal_for_response(cluster.radius_meters),
        "score": _score_for_response(cluster.score),
        "riskLevel": cluster.risk_level or None,
        "explanation": cluster.explanation or None,
        "metadata": cluster.metadata,
        "createdAt": cluster.created_at.isoformat(),
        "updatedAt": cluster.updated_at.isoformat(),
        "integrationClient": {
            "code": cluster.integration_client.code,
            "name": cluster.integration_client.name,
        },
    }


def _replayed_payload(response_payload):
    payload = dict(response_payload or {})
    payload["status"] = "replayed"
    return payload


def _score_for_response(score):
    if score is None:
        return None
    return float(score)


def _decimal_for_response(value):
    if value is None:
        return None
    return float(value)


def _create_action_log(
    *,
    request,
    integration_client,
    target_id,
    result_status,
    result_summary,
    payload=None,
    raw_payload=None,
    idempotency_key="",
    external_action_id="",
):
    payload_value = raw_payload if raw_payload is not None else payload
    payload_hash_value = payload_hash(payload_value) if payload_value is not None else ""

    return IntegrationActionLog.objects.create(
        integration_client=integration_client,
        action_type=ACTION_AI_CREATE_COMMENT,
        required_scope=IntegrationScope.AI_CREATE_COMMENT,
        target_type=TARGET_REPORT,
        target_id=target_id,
        idempotency_key=idempotency_key,
        external_action_id=external_action_id,
        payload_hash=payload_hash_value,
        request_headers_summary=_headers_summary(request),
        result_status=result_status,
        result_summary=secret_safe_summary(result_summary),
    )


def _create_risk_action_log(
    *,
    request,
    integration_client,
    target_type,
    target_id,
    result_status,
    result_summary,
    payload=None,
    raw_payload=None,
    idempotency_key="",
    external_assessment_id="",
):
    payload_value = raw_payload if raw_payload is not None else payload
    payload_hash_value = payload_hash(payload_value) if payload_value is not None else ""

    return IntegrationActionLog.objects.create(
        integration_client=integration_client,
        action_type=ACTION_RISK_UPDATE,
        required_scope=IntegrationScope.RISK_UPDATE,
        target_type=target_type,
        target_id=target_id,
        idempotency_key=idempotency_key,
        external_action_id=external_assessment_id,
        payload_hash=payload_hash_value,
        request_headers_summary=_headers_summary(request),
        result_status=result_status,
        result_summary=secret_safe_summary(result_summary),
    )


def _create_incident_read_action_log(
    *,
    request,
    integration_client,
    result_status,
    result_summary,
    target_id="",
):
    query_payload = _query_payload(request)

    return IntegrationActionLog.objects.create(
        integration_client=integration_client,
        action_type=ACTION_INCIDENT_READ,
        required_scope=IntegrationScope.INCIDENT_READ,
        target_type=TARGET_REPORT if target_id else "",
        target_id=target_id,
        payload_hash=payload_hash(query_payload) if query_payload else "",
        request_headers_summary=_headers_summary(request),
        result_status=result_status,
        result_summary=secret_safe_summary(result_summary),
    )


def _create_ai_image_action_log(
    *,
    request,
    integration_client,
    action_type,
    result_status,
    result_summary,
    target_type="",
    target_id="",
):
    return IntegrationActionLog.objects.create(
        integration_client=integration_client,
        action_type=action_type,
        required_scope=IntegrationScope.AI_READ_IMAGES,
        target_type=target_type,
        target_id=target_id,
        payload_hash="",
        request_headers_summary=_headers_summary(request),
        result_status=result_status,
        result_summary=secret_safe_summary(result_summary),
    )


def _create_census_read_action_log(
    *,
    request,
    integration_client,
    result_status,
    result_summary,
    target_type="",
    target_id="",
):
    query_payload = _query_payload(request)

    return IntegrationActionLog.objects.create(
        integration_client=integration_client,
        action_type=ACTION_CENSUS_READ,
        required_scope=IntegrationScope.CENSUS_READ,
        target_type=target_type,
        target_id=target_id,
        payload_hash=payload_hash(query_payload) if query_payload else "",
        request_headers_summary=_headers_summary(request),
        result_status=result_status,
        result_summary=secret_safe_summary(result_summary),
    )


def _create_cluster_action_log(
    *,
    request,
    integration_client,
    action_type,
    result_status,
    result_summary,
    target_type="",
    target_id="",
    payload=None,
    raw_payload=None,
    idempotency_key="",
    external_cluster_id="",
):
    payload_value = raw_payload if raw_payload is not None else payload
    query_payload = _query_payload(request)
    if payload_value is not None:
        payload_hash_value = payload_hash(payload_value)
    elif query_payload:
        payload_hash_value = payload_hash(query_payload)
    else:
        payload_hash_value = ""

    return IntegrationActionLog.objects.create(
        integration_client=integration_client,
        action_type=action_type,
        required_scope=IntegrationScope.CLUSTER_WRITE_RESULT,
        target_type=target_type,
        target_id=target_id,
        idempotency_key=idempotency_key,
        external_action_id=external_cluster_id,
        payload_hash=payload_hash_value,
        request_headers_summary=_headers_summary(request),
        result_status=result_status,
        result_summary=secret_safe_summary(result_summary),
    )


def _headers_summary(request):
    return secret_safe_summary(
        {
            "Authorization": request.headers.get("Authorization", ""),
            "Content-Type": request.headers.get("Content-Type", ""),
            "Idempotency-Key": request.headers.get("Idempotency-Key", ""),
        }
    )


def _query_payload(request):
    payload = {}
    for key in sorted(request.GET.keys()):
        values = request.GET.getlist(key)
        payload[key] = values[0] if len(values) == 1 else values
    return payload


def _action_id_for_record(record):
    if record.action_log_id is None:
        return ""
    return str(record.action_log.action_id)


def _error_response(*, status, code, message, headers=None):
    response = JsonResponse(
        {
            "error": {
                "code": code,
                "message": message,
            }
        },
        status=status,
    )
    if headers:
        for name, value in headers.items():
            response[name] = value
    return response
