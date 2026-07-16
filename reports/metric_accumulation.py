"""
Configurable metric accumulation for incident reports + follow-ups.

Config lives on ReportType.metric_accumulation. Totals are derived on read
from IncidentReport.data and FollowUpReport.data (no write-time mutation).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

SUPPORTED_OPS = frozenset({"sum", "latest"})


def extract_number(data: Optional[dict], field: str) -> Optional[int]:
    """Pull a numeric value from form JSON data. Returns None if missing/invalid."""
    if not data or not field:
        return None
    raw = data.get(field)
    if raw is None:
        return None
    # Multiple-choice style wrappers sometimes nest value
    if isinstance(raw, dict):
        raw = raw.get("value", raw.get("int", raw.get("number")))
    if raw is None or raw == "":
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        try:
            return int(float(raw))
        except (TypeError, ValueError):
            return None


def parse_metric_specs(config: Any) -> List[dict]:
    """
    Validate and normalize metric_accumulation config.
    Invalid / empty config → []. Soft-fail (never raises for bad tenant data).
    """
    if not config or not isinstance(config, dict):
        return []
    metrics = config.get("metrics")
    if not isinstance(metrics, list):
        return []

    specs: List[dict] = []
    for item in metrics:
        if not isinstance(item, dict):
            continue
        metric_id = item.get("id") or item.get("reportField")
        report_field = item.get("reportField")
        followup_field = item.get("followupField") or report_field
        op = (item.get("op") or "sum").strip().lower()
        if not metric_id or not report_field:
            continue
        if op not in SUPPORTED_OPS:
            logger.warning(
                "metric_accumulation: unsupported op %r for metric %r; skipped",
                op,
                metric_id,
            )
            continue
        specs.append(
            {
                "id": str(metric_id),
                "label": item.get("label") or str(metric_id),
                "reportField": str(report_field),
                "followupField": str(followup_field),
                "op": op,
                "type": item.get("type") or "integer",
            }
        )
    return specs


def accumulate_metrics(
    report_data: Optional[dict],
    followup_data_list: List[Optional[dict]],
    config: Any,
) -> Dict[str, Any]:
    """
    Pure accumulation from config + data blobs.

    followup_data_list should be ordered by created_at ascending for `latest`.
    """
    specs = parse_metric_specs(config)
    if not specs:
        return {"version": 1, "metrics": []}

    results = []
    for spec in specs:
        report_value = extract_number(report_data, spec["reportField"])
        followup_values: List[Optional[int]] = [
            extract_number(fu, spec["followupField"]) for fu in followup_data_list
        ]

        if spec["op"] == "sum":
            total = report_value if report_value is not None else 0
            for v in followup_values:
                total += v if v is not None else 0
            value = total
        else:  # latest
            value = report_value
            for v in followup_values:
                if v is not None:
                    value = v
            if value is None:
                value = 0

        results.append(
            {
                "id": spec["id"],
                "label": spec["label"],
                "op": spec["op"],
                "reportValue": report_value if report_value is not None else 0,
                "followupValues": [v if v is not None else 0 for v in followup_values],
                "value": value,
            }
        )

    return {"version": 1, "metrics": results}


def accumulate_incident_metrics(incident) -> Dict[str, Any]:
    """
    Compute accumulation for an IncidentReport instance.
    Uses report_type.metric_accumulation and ordered followups.
    """
    report_type = getattr(incident, "report_type", None)
    config = getattr(report_type, "metric_accumulation", None) if report_type else None
    followups = list(
        incident.followups.order_by("created_at").values_list("data", flat=True)
    )
    return accumulate_metrics(incident.data, followups, config)
