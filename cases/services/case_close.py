"""Layered case close: Layer1 lifecycle + Layer2 configurable payload."""

from typing import Any, Dict, Optional

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


def validate_close_payload(
    definition: Optional[dict],
    payload: dict,
    *,
    source: str,
) -> dict:
    """
    Validate payload against close_definition.
    requiredOn: list including 'officer' and/or 'system'.
    Empty/missing definition: payload must be a dict (may be empty).
    """
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        raise ValidationError("close payload must be an object")

    # System path: always empty payload (no program fields).
    if source == "system":
        return {}

    if not definition:
        return dict(payload)

    fields = definition.get("fields") or []
    if not isinstance(fields, list):
        raise ValidationError("close_definition.fields must be a list")

    cleaned: Dict[str, Any] = {}
    field_ids = set()

    for field in fields:
        if not isinstance(field, dict):
            continue
        field_id = field.get("id")
        if not field_id or not isinstance(field_id, str):
            continue
        field_ids.add(field_id)
        field_type = field.get("type") or "text"
        required_on = field.get("requiredOn") or []
        if not isinstance(required_on, list):
            required_on = []

        value = payload.get(field_id, None)
        is_required = source in required_on

        if value is None or value == "":
            if is_required:
                raise ValidationError(f"close payload field '{field_id}' is required")
            continue

        if field_type == "text":
            if not isinstance(value, str):
                raise ValidationError(f"close payload field '{field_id}' must be text")
            cleaned[field_id] = value.strip()
            if is_required and not cleaned[field_id]:
                raise ValidationError(f"close payload field '{field_id}' is required")
        elif field_type == "species_counts":
            if not isinstance(value, dict):
                raise ValidationError(
                    f"close payload field '{field_id}' must be an object of species counts"
                )
            counts = {}
            for species, count in value.items():
                if not isinstance(species, str) or not species.strip():
                    raise ValidationError(
                        f"close payload field '{field_id}' has invalid species key"
                    )
                try:
                    n = int(count)
                except (TypeError, ValueError):
                    raise ValidationError(
                        f"close payload field '{field_id}' count for '{species}' must be an integer"
                    )
                if n < 0:
                    raise ValidationError(
                        f"close payload field '{field_id}' count for '{species}' must be >= 0"
                    )
                counts[species] = n
            if is_required and len(counts) == 0:
                raise ValidationError(f"close payload field '{field_id}' is required")
            cleaned[field_id] = counts
        else:
            # Unknown types: accept JSON-serializable as-is if present
            cleaned[field_id] = value

    # Preserve unknown keys from client (non-schema) only if definition empty handled above.
    # Strict: only schema field ids stored when definition present.
    return cleaned


@transaction.atomic
def close_case(
    case,
    *,
    source: str,
    actor=None,
    payload: Optional[dict] = None,
    stopped_at=None,
    status_label: Optional[str] = None,
):
    """
    Atomic layered close.
    source: Case.CloseSource.OFFICER | SYSTEM (or 'officer' | 'system')
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
    else:
        source_value = Case.CloseSource.SYSTEM
        actor = None

    definition = get_close_definition_for_case(case)
    cleaned_payload = validate_close_payload(
        definition, payload or {}, source=source_value
    )

    schema_version = None
    if definition and isinstance(definition.get("version"), int):
        schema_version = definition["version"]

    case.stopped_at = stopped_at or timezone.now()
    case.close_source = source_value
    case.closed_by = actor
    case.is_finished = True
    case.close_payload = cleaned_payload
    case.close_payload_schema_version = schema_version
    if status_label is not None:
        case.status_label = status_label
    elif not case.status_label:
        case.status_label = "Closed"

    case.save(
        update_fields=[
            "stopped_at",
            "close_source",
            "closed_by",
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
    # Merge shallow for draft editing
    current = dict(case.close_payload) if isinstance(case.close_payload, dict) else {}
    current.update(payload)
    case.close_payload = current
    case.save(update_fields=["close_payload", "updated_at"])
    return case
