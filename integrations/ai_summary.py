from datetime import timedelta

from django.core.exceptions import ValidationError
from django.utils import timezone

from accounts.models import AuthorityUser
from integrations.constants import (
    AI_SUMMARY_DEBOUNCE_SECONDS,
    AI_SUMMARY_PURPOSE,
    AI_SUMMARY_USER_PROMPT_MAX_LENGTH,
    IntegrationEventType,
)
from integrations.models import IntegrationEvent
from integrations.policy import (
    FEATURE_AI,
    IntegrationPolicyDenied,
    assert_integration_feature_enabled,
)
from reports.models import IncidentReport


class AiSummaryRequestError(Exception):
    def __init__(self, code, message, field=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.field = field


def normalize_user_prompt(value):
    if value is None:
        return ""
    if not isinstance(value, str):
        raise AiSummaryRequestError(
            "prompt_too_long",
            "User prompt must be a string.",
            field="userPrompt",
        )
    return value.strip()


def request_officer_ai_summary(
    *,
    user,
    report_id,
    user_prompt=None,
    enqueue_delivery_tasks=True,
):
    from integrations.webhooks import (
        has_active_ai_evaluation_endpoint,
        record_ai_evaluation_requested_event,
    )

    user_prompt_text = normalize_user_prompt(user_prompt)
    if len(user_prompt_text) > AI_SUMMARY_USER_PROMPT_MAX_LENGTH:
        raise AiSummaryRequestError(
            "prompt_too_long",
            "User prompt must be 2000 characters or fewer.",
            field="userPrompt",
        )

    try:
        report = IncidentReport.objects.prefetch_related("relevant_authorities").get(
            pk=report_id
        )
    except (IncidentReport.DoesNotExist, ValueError, TypeError, ValidationError):
        raise AiSummaryRequestError(
            "incident_not_found",
            "Incident was not found in the selected tenant.",
        )

    permission_code = officer_ai_summary_permission_code(user, report)
    if permission_code:
        raise AiSummaryRequestError(
            permission_code,
            "You are not authorized to request an AI summary.",
        )

    try:
        assert_integration_feature_enabled(FEATURE_AI)
    except IntegrationPolicyDenied as exc:
        raise AiSummaryRequestError(exc.code, exc.message)

    if ai_evaluation_requested_in_flight(report.id):
        raise AiSummaryRequestError(
            "already_in_flight",
            "An AI summary request is already in progress for this report.",
        )

    if not has_active_ai_evaluation_endpoint():
        raise AiSummaryRequestError(
            "no_webhook_endpoint",
            "No active AI webhook endpoint is configured for this tenant.",
        )

    result = record_ai_evaluation_requested_event(
        report_id=report.id,
        requested_by_user=user,
        purpose=AI_SUMMARY_PURPOSE,
        user_prompt=user_prompt_text,
        enqueue_delivery_tasks=enqueue_delivery_tasks,
    )
    if result.event is None:
        raise AiSummaryRequestError(
            "ai_disabled",
            "AI integration is disabled for this tenant.",
        )

    return {
        "event_id": result.event.event_id,
        "report_id": report.id,
        "status": "queued",
    }


def officer_ai_summary_permission_code(user, report):
    if user is None or not getattr(user, "is_authenticated", False):
        return "permission_denied"
    if user.is_superuser:
        return None
    if user.is_authority_role_in([AuthorityUser.Role.REPORTER]):
        return "permission_denied"
    if not user.is_authority_user:
        return "permission_denied"
    if not user.is_authority_role_in(
        [AuthorityUser.Role.ADMIN, AuthorityUser.Role.OFFICER]
    ):
        return "permission_denied"

    authority = user.authorityuser.authority
    if not report.relevant_authorities.filter(
        pk__in=[item.pk for item in authority.all_inherits_down()]
    ).exists():
        return "permission_denied"
    return None


def ai_summary_enabled_for_user(user):
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    if user.is_authority_role_in([AuthorityUser.Role.REPORTER]):
        return False
    allowed = user.is_superuser or user.is_authority_role_in(
        [AuthorityUser.Role.ADMIN, AuthorityUser.Role.OFFICER]
    )
    if not allowed:
        return False

    from integrations.policy import is_ai_enabled_flag

    return is_ai_enabled_flag()


def ai_evaluation_requested_in_flight(
    report_id, *, now=None, window_seconds=AI_SUMMARY_DEBOUNCE_SECONDS
):
    now = now or timezone.now()
    return IntegrationEvent.objects.filter(
        event_type=IntegrationEventType.AI_EVALUATION_REQUESTED,
        source_app="reports",
        subject_type="reports.IncidentReport",
        subject_id=str(report_id),
        produced_at__gte=now - timedelta(seconds=window_seconds),
        deleted_at__isnull=True,
    ).exists()
