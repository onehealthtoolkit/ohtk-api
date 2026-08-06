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
    report = getattr(case, "report", None)
    if report is None:
        return None
    report_type = getattr(report, "report_type", None)
    if report_type is None:
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
        case.status_label = "Closed by system"
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
    CO3: close open cases with no activity for `days`.
    Runs in the current tenant schema. Returns count closed.

    If days is None, uses tenant Configuration `cases.auto_close_days`
    (see cases.auto_close_config.get_case_auto_close_days).
    """
    from datetime import timedelta

    from cases.auto_close_config import get_case_auto_close_days
    from cases.models import Case

    if days is None:
        days = get_case_auto_close_days()
    days = int(days)
    if days < 1:
        raise ValidationError("days must be >= 1")

    cutoff = timezone.now() - timedelta(days=days)
    closed = 0
    qs = (
        Case.objects.filter(stopped_at__isnull=True, is_finished=False)
        .select_related("report")
        .iterator(chunk_size=100)
    )
    for case in qs:
        try:
            last = case_last_activity_at(case)
        except Exception:
            continue
        if last is None or last > cutoff:
            continue
        try:
            close_case(case, source="system", actor=None, payload={})
            closed += 1
        except ValidationError:
            continue
    return closed
