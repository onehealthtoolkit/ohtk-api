"""Layered case close: Layer1 lifecycle + Layer2 configurable payload.

close_definition is a full opsv form JSON (same shape as report/transition forms):
  { "id", "sections": [{ "label", "questions": [{ "label", "fields": [{ "id"|"name", "type", "required", ...}] }] }], ... }

Legacy thin shape is still accepted for older seeds/tests:
  { "fields": [{ "id", "type", "requiredOn": ["officer"] }] }
"""

from typing import Any, Dict, List, Optional

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone


def get_close_definition_for_case(case) -> Optional[dict]:
    """
    Load ReportType.close_definition for the case's incident report.

    Re-reads ReportType from the DB so callers are not affected by a stale
    related-object cache after definition updates in the same process.
    """
    report = getattr(case, "report", None)
    if report is None:
        return None
    report_type_id = getattr(report, "report_type_id", None)
    if not report_type_id:
        report_type = getattr(report, "report_type", None)
        report_type_id = getattr(report_type, "pk", None) if report_type else None
    if not report_type_id:
        return None
    from reports.models import ReportType

    try:
        report_type = ReportType.objects.only("close_definition").get(
            pk=report_type_id
        )
    except ReportType.DoesNotExist:
        return None
    definition = getattr(report_type, "close_definition", None)
    if not definition or not isinstance(definition, dict):
        return None
    return definition


def extract_close_fields(definition: Optional[dict]) -> List[dict]:
    """
    Flatten field descriptors from close_definition.
    Returns list of {name, type, required} for officer validation.
    """
    if not definition or not isinstance(definition, dict):
        return []

    # Full opsv form
    sections = definition.get("sections")
    if isinstance(sections, list):
        fields: List[dict] = []
        for section in sections:
            if not isinstance(section, dict):
                continue
            for question in section.get("questions") or []:
                if not isinstance(question, dict):
                    continue
                for field in question.get("fields") or []:
                    if not isinstance(field, dict):
                        continue
                    name = field.get("name") or field.get("id")
                    if not name or not isinstance(name, str):
                        continue
                    fields.append(
                        {
                            "name": name,
                            "type": field.get("type") or "text",
                            "required": bool(field.get("required")),
                            "min": field.get("min"),
                            "max": field.get("max"),
                        }
                    )
        return fields

    # Legacy thin list
    legacy = definition.get("fields") or []
    if not isinstance(legacy, list):
        return []
    fields = []
    for field in legacy:
        if not isinstance(field, dict):
            continue
        name = field.get("id") or field.get("name")
        if not name or not isinstance(name, str):
            continue
        required_on = field.get("requiredOn") or []
        if not isinstance(required_on, list):
            required_on = []
        fields.append(
            {
                "name": name,
                "type": field.get("type") or "text",
                # thin schema used requiredOn: ["officer"]
                "required": "officer" in required_on,
                "min": field.get("min"),
                "max": field.get("max"),
            }
        )
    return fields


def _validate_text(name: str, value: Any, *, required: bool) -> Optional[str]:
    if value is None or value == "":
        if required:
            raise ValidationError(f"close payload field '{name}' is required")
        return None
    if not isinstance(value, str):
        raise ValidationError(f"close payload field '{name}' must be text")
    cleaned = value.strip()
    if required and not cleaned:
        raise ValidationError(f"close payload field '{name}' is required")
    return cleaned


def _validate_integer(
    name: str, value: Any, *, required: bool, min_v=None, max_v=None
) -> Optional[int]:
    if value is None or value == "":
        if required:
            raise ValidationError(f"close payload field '{name}' is required")
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValidationError(f"close payload field '{name}' must be an integer")
    try:
        if isinstance(value, str):
            raw = value.strip()
            if raw == "":
                if required:
                    raise ValidationError(f"close payload field '{name}' is required")
                return None
            n = int(raw)
        else:
            n = int(value)
    except (TypeError, ValueError):
        raise ValidationError(f"close payload field '{name}' must be an integer")
    if min_v is not None and n < int(min_v):
        raise ValidationError(f"close payload field '{name}' must be >= {int(min_v)}")
    if max_v is not None and n > int(max_v):
        raise ValidationError(f"close payload field '{name}' must be <= {int(max_v)}")
    return n


def validate_close_payload(
    definition: Optional[dict],
    payload: dict,
    *,
    source: str,
) -> dict:
    """
    Validate payload against close_definition (opsv form or legacy thin fields).
    Empty/missing definition: payload must be a dict (may be empty / pass-through).
    System source: always empty payload.
    """
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        raise ValidationError("close payload must be an object")

    if source == "system":
        return {}

    if not definition:
        return dict(payload)

    fields = extract_close_fields(definition)
    # If definition present but no extractable fields (malformed), allow empty strict
    cleaned: Dict[str, Any] = {}

    for field in fields:
        name = field["name"]
        field_type = field["type"] or "text"
        required = bool(field.get("required"))
        # Only officer path reaches here; required applies to officer close.
        value = payload.get(name, None)

        if field_type in ("text", "textarea"):
            result = _validate_text(name, value, required=required)
            if result is not None:
                cleaned[name] = result
        elif field_type == "integer":
            min_v = field.get("min")
            if min_v is None:
                min_v = 0
            result = _validate_integer(
                name,
                value,
                required=required,
                min_v=min_v,
                max_v=field.get("max"),
            )
            if result is not None:
                cleaned[name] = result
        else:
            # Unknown opsv types: store as-is if present
            if value is None or value == "":
                if required:
                    raise ValidationError(f"close payload field '{name}' is required")
                continue
            cleaned[name] = value

    return cleaned


# Officer finish outcomes (CO2b)
OUTCOME_CLOSE_CASE = "close_case"
OUTCOME_FALSE_POSITIVE = "false_positive"
OFFICER_OUTCOMES = (OUTCOME_CLOSE_CASE, OUTCOME_FALSE_POSITIVE)

# Service account username for system-generated audit comments (auto-close).
SYSTEM_AUDIT_USERNAME = "system"


def _format_close_payload_for_audit(payload: Optional[dict]) -> str:
    """Human-readable payload lines for comment body (skip empty / outcome key)."""
    if not isinstance(payload, dict):
        return ""
    skip = {"close_outcome"}
    lines = []
    for key, value in payload.items():
        if key in skip or value is None or value == "":
            continue
        label = str(key).replace("_", " ")
        lines.append(f"{label}: {value}")
    return "\n".join(lines)


def _resolve_system_audit_user():
    """Inactive system user for automatic-close audit comments."""
    from accounts.models import User

    user, _ = User.objects.get_or_create(
        username=SYSTEM_AUDIT_USERNAME,
        defaults={
            "first_name": "System",
            "last_name": "",
            "is_active": False,
            "is_staff": False,
            "is_superuser": False,
        },
    )
    return user


def ensure_case_thread(case):
    """Return case discussion thread, creating one if missing."""
    from threads.models import Thread

    thread = getattr(case, "thread", None)
    if thread is not None:
        return thread
    report = getattr(case, "report", None)
    if report is not None:
        thread = getattr(report, "thread", None)
        if thread is not None:
            case.thread = thread
            case.save(update_fields=["thread", "updated_at"])
            return thread
    thread = Thread.objects.create()
    case.thread = thread
    case.save(update_fields=["thread", "updated_at"])
    return thread


def post_case_audit_comment(case, *, actor, body: str):
    """
    Append an audit line to the case Comments thread.
    actor may be None for system actions (uses inactive username=system).
    """
    from threads.models import Comment

    text = (body or "").strip()
    if not text:
        return None
    user = actor if actor is not None else _resolve_system_audit_user()
    thread = ensure_case_thread(case)
    return Comment.objects.create(thread=thread, body=text, created_by=user)


def build_close_audit_body(
    *,
    source: str,
    outcome: str = "",
    payload: Optional[dict] = None,
    action: str = "close",
) -> str:
    """
    action:
      close — initial finish
      complete_after_auto_close — officer fills data after system timeout
      superuser_edit — superuser edits finished close data
    """
    payload_lines = _format_close_payload_for_audit(payload)
    source_value = source.value if hasattr(source, "value") else source

    if action == "complete_after_auto_close":
        head = "[Close data] Added after automatic close"
    elif action == "superuser_edit":
        head = "[Close data] Superuser edit"
    elif source_value in ("system",):
        head = "[Automatic close] Case finished by system after inactivity"
    elif outcome == OUTCOME_FALSE_POSITIVE:
        head = "[Case close] False positive"
    else:
        head = "[Case close] Close case"

    if payload_lines:
        return f"{head}\n{payload_lines}"
    if action == "close" and source_value in ("system",):
        return f"{head}\nNo close data recorded."
    return head


@transaction.atomic
def close_case(
    case,
    *,
    source: str,
    actor=None,
    payload: Optional[dict] = None,
    outcome: Optional[str] = None,
    stopped_at=None,
    status_label: Optional[str] = None,
):
    """
    Atomic layered close.
    source: officer | system
    outcome (officer): close_case | false_positive
    system: outcome forced empty, payload {}
    """
    from cases.models import Case

    if case.stopped_at is not None:
        raise ValidationError("Case is already closed")

    source_value = source
    if hasattr(source, "value"):
        source_value = source.value

    if source_value not in (
        Case.CloseSource.OFFICER,
        Case.CloseSource.SYSTEM,
        "officer",
        "system",
    ):
        raise ValidationError("invalid close source")

    if source_value in (Case.CloseSource.OFFICER, "officer"):
        source_value = Case.CloseSource.OFFICER
        if actor is None:
            raise ValidationError("officer close requires actor")
        outcome_value = (outcome or OUTCOME_CLOSE_CASE).strip()
        if outcome_value not in OFFICER_OUTCOMES:
            raise ValidationError(
                f"invalid close outcome '{outcome_value}' "
                f"(expected one of {', '.join(OFFICER_OUTCOMES)})"
            )
    else:
        source_value = Case.CloseSource.SYSTEM
        actor = None
        outcome_value = ""

    definition = get_close_definition_for_case(case)
    schema_version = None

    if source_value == Case.CloseSource.SYSTEM:
        cleaned_payload = {}
    elif outcome_value == OUTCOME_FALSE_POSITIVE:
        # False positive: no program close_definition requirements (no stamp_out).
        raw = payload if isinstance(payload, dict) else {}
        cleaned_payload = {
            k: v for k, v in raw.items() if v is not None and v != ""
        }
        cleaned_payload["close_outcome"] = OUTCOME_FALSE_POSITIVE
    else:
        # close_case: validate against ReportType.close_definition
        cleaned_payload = validate_close_payload(
            definition, payload or {}, source=source_value
        )
        cleaned_payload["close_outcome"] = OUTCOME_CLOSE_CASE
        if definition and isinstance(definition.get("version"), int):
            schema_version = definition["version"]

    case.stopped_at = stopped_at or timezone.now()
    case.close_source = source_value
    case.closed_by = actor
    case.close_outcome = outcome_value
    case.is_finished = True
    case.close_payload = cleaned_payload
    case.close_payload_schema_version = schema_version
    if status_label is not None:
        case.status_label = status_label
    elif source_value == Case.CloseSource.SYSTEM:
        # CO3: always mark so list/legacy never keep a stale open workflow label.
        case.status_label = "Automatically closed"
    elif not case.status_label:
        if outcome_value == OUTCOME_FALSE_POSITIVE:
            case.status_label = "False positive"
        else:
            case.status_label = "Closed"

    case.save(
        update_fields=[
            "stopped_at",
            "close_source",
            "closed_by",
            "close_outcome",
            "is_finished",
            "close_payload",
            "close_payload_schema_version",
            "status_label",
            "updated_at",
        ]
    )
    post_case_audit_comment(
        case,
        actor=actor,
        body=build_close_audit_body(
            source=source_value,
            outcome=outcome_value,
            payload=cleaned_payload,
            action="close",
        ),
    )
    return case


def update_open_case_close_payload(case, payload: dict) -> "Case":
    """Update Layer2 draft while case is open (no close)."""
    if case.stopped_at is not None:
        raise ValidationError("Cannot update close payload on a closed case")
    if not isinstance(payload, dict):
        raise ValidationError("close payload must be an object")
    current = dict(case.close_payload) if isinstance(case.close_payload, dict) else {}
    current.update(payload)
    case.close_payload = current
    case.save(update_fields=["close_payload", "updated_at"])
    return case


@transaction.atomic
def complete_system_closed_case(case, *, actor, payload: Optional[dict] = None):
    """
    CO3b: officer fills Layer2 (test_result, stamp_out, …) after automatic close.

    Does not reopen the case: keeps stopped_at, close_source=system, is_finished.
    Sets close_outcome=close_case and validates payload like officer close.
    """
    from cases.models import Case

    if case.stopped_at is None or not case.is_finished:
        raise ValidationError("Case is not closed")
    if case.close_source != Case.CloseSource.SYSTEM:
        raise ValidationError(
            "Only automatically closed cases can receive late close data"
        )
    if actor is None:
        raise ValidationError("completing close data requires actor")

    definition = get_close_definition_for_case(case)
    cleaned_payload = validate_close_payload(
        definition, payload or {}, source=Case.CloseSource.OFFICER
    )
    cleaned_payload["close_outcome"] = OUTCOME_CLOSE_CASE
    schema_version = None
    if definition and isinstance(definition.get("version"), int):
        schema_version = definition["version"]

    case.close_payload = cleaned_payload
    case.close_outcome = OUTCOME_CLOSE_CASE
    case.close_payload_schema_version = schema_version
    # Keep lifecycle as system timeout; record who supplied the late data.
    case.closed_by = actor
    case.save(
        update_fields=[
            "close_payload",
            "close_outcome",
            "close_payload_schema_version",
            "closed_by",
            "updated_at",
        ]
    )
    post_case_audit_comment(
        case,
        actor=actor,
        body=build_close_audit_body(
            source=Case.CloseSource.SYSTEM,
            outcome=OUTCOME_CLOSE_CASE,
            payload=cleaned_payload,
            action="complete_after_auto_close",
        ),
    )
    return case


@transaction.atomic
def update_finished_case_close_data(case, *, actor, payload: Optional[dict] = None):
    """
    Superuser-only: edit Layer2 close data on any finished case without reopening.

    Keeps stopped_at, close_source, is_finished, closed_by (original finisher).
    """
    from cases.models import Case

    if actor is None or not getattr(actor, "is_superuser", False):
        raise ValidationError("Only superuser can edit finished close data")
    if case.stopped_at is None or not case.is_finished:
        raise ValidationError("Case is not closed")

    outcome = (case.close_outcome or "").strip()
    update_fields = ["close_payload", "updated_at"]

    if outcome == OUTCOME_FALSE_POSITIVE:
        raw = payload if isinstance(payload, dict) else {}
        cleaned_payload = {
            k: v for k, v in raw.items() if v is not None and v != ""
        }
        cleaned_payload["close_outcome"] = OUTCOME_FALSE_POSITIVE
        case.close_payload = cleaned_payload
    else:
        # Officer close_case, system timeout, or empty outcome after auto-close.
        definition = get_close_definition_for_case(case)
        cleaned_payload = validate_close_payload(
            definition, payload or {}, source=Case.CloseSource.OFFICER
        )
        cleaned_payload["close_outcome"] = OUTCOME_CLOSE_CASE
        case.close_payload = cleaned_payload
        if outcome != OUTCOME_CLOSE_CASE:
            case.close_outcome = OUTCOME_CLOSE_CASE
            update_fields.append("close_outcome")
        if definition and isinstance(definition.get("version"), int):
            case.close_payload_schema_version = definition["version"]
            update_fields.append("close_payload_schema_version")

    case.save(update_fields=update_fields)
    post_case_audit_comment(
        case,
        actor=actor,
        body=build_close_audit_body(
            source=case.close_source or Case.CloseSource.OFFICER,
            outcome=case.close_outcome or "",
            payload=case.close_payload if isinstance(case.close_payload, dict) else {},
            action="superuser_edit",
        ),
    )
    return case


def case_last_activity_at(case):
    """
    Activity clock for CO3 timeout.
    Latest of: case.created_at, linked report created_at, latest follow-up created_at.
    """
    from reports.models import FollowUpReport

    candidates = [case.created_at]
    report = getattr(case, "report", None)
    if report is not None and report.created_at:
        candidates.append(report.created_at)
    if report is not None:
        latest_fu = (
            FollowUpReport.objects.filter(incident=report)
            .order_by("-created_at")
            .values_list("created_at", flat=True)
            .first()
        )
        if latest_fu:
            candidates.append(latest_fu)
    return max(c for c in candidates if c is not None)


def auto_close_stale_open_cases(*, days: Optional[int] = None) -> int:
    """
    CO3 / D07: system-finish open cases that meet the risk-tiered clock.

    Default windows: LOW = 14 days silence; MEDIUM/HIGH/CRITICAL/none = 21 days
    after derived ongoing=0 or no new sick.

    days: optional override of **both** windows (ops one-shot / tests).
    Tenant `cases.auto_close_days` is not the D07 rule.
    """
    from cases.models import Case
    from cases.services.auto_close_eligibility import (
        AUTO_CLOSE_LR_DAYS,
        AUTO_CLOSE_MRHR_DAYS,
        should_system_auto_close,
    )

    lr_days = AUTO_CLOSE_LR_DAYS
    mrhr_days = AUTO_CLOSE_MRHR_DAYS
    if days is not None:
        days = int(days)
        if days < 0:
            raise ValidationError("days must be >= 0")
        lr_days = mrhr_days = days

    now = timezone.now()
    closed = 0
    qs = (
        Case.objects.filter(stopped_at__isnull=True, is_finished=False)
        .select_related("report")
        .iterator(chunk_size=100)
    )
    for case in qs:
        try:
            with transaction.atomic():
                if not should_system_auto_close(
                    case, now=now, lr_days=lr_days, mrhr_days=mrhr_days
                ):
                    continue
                close_case(case, source="system", actor=None, payload={})
                closed += 1
        except ValidationError:
            continue
        except Exception:
            continue
    return closed
