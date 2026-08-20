"""D07 risk-tiered CO3 auto-close eligibility.

See wiki/decision-D07-risk-tiered-auto-close.md.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, List, Optional, Tuple

from django.utils import timezone

from reports.metric_accumulation import extract_number

BAND_LR = "lr"
BAND_MRHR = "mrhr"

AUTO_CLOSE_LR_DAYS = 14
AUTO_CLOSE_MRHR_DAYS = 21

SICK_FIELD = "num_sick"
DEAD_FIELD = "num_dead"
RECOVER_FIELD = "num_recover"


def _count(data: Optional[dict], field: str) -> int:
    if not isinstance(data, dict):
        return 0
    value = extract_number(data, field)
    return 0 if value is None else int(value)


def case_auto_close_band(case) -> str:
    """LOW → LR. MEDIUM/HIGH/CRITICAL/none → MR/HR."""
    from integrations.models import RiskAssessment
    from integrations.services import get_current_risk_assessment

    report = getattr(case, "report", None)
    if report is None:
        return BAND_MRHR
    assessment = get_current_risk_assessment(report=report)
    if assessment is None:
        return BAND_MRHR
    if assessment.level == RiskAssessment.Level.LOW:
        return BAND_LR
    return BAND_MRHR


def _events(case) -> List[Tuple[Any, dict]]:
    from reports.models import FollowUpReport

    report = getattr(case, "report", None)
    events: List[Tuple[Any, dict]] = []
    if report is not None and report.created_at:
        data = report.data if isinstance(report.data, dict) else {}
        events.append((report.created_at, data))
        followups = FollowUpReport.objects.filter(incident=report).order_by(
            "created_at"
        )
        for followup in followups:
            if not followup.created_at:
                continue
            fu_data = followup.data if isinstance(followup.data, dict) else {}
            events.append((followup.created_at, fu_data))
    elif getattr(case, "created_at", None):
        events.append((case.created_at, {}))
    return events


def case_auto_close_clock(case) -> Optional[Dict[str, Any]]:
    """Running sick series + D07 timestamps. None if the case has no clock."""
    events = _events(case)
    if not events:
        return None

    last_activity_at = events[-1][0]
    last_sick_increase_at = events[0][0]
    total_sick = 0
    total_dead = 0
    total_recover = 0
    ongoings: List[Tuple[Any, int]] = []

    for created_at, data in events:
        sick = _count(data, SICK_FIELD)
        dead = _count(data, DEAD_FIELD)
        recover = _count(data, RECOVER_FIELD)
        total_sick += sick
        total_dead += dead
        total_recover += recover
        ongoing = max(0, total_sick - total_dead - total_recover)
        ongoings.append((created_at, ongoing))
        if sick > 0:
            last_sick_increase_at = created_at

    first_cleared_at = None
    if ongoings and ongoings[-1][1] == 0:
        for created_at, ongoing in reversed(ongoings):
            if ongoing != 0:
                break
            first_cleared_at = created_at

    return {
        "band": case_auto_close_band(case),
        "last_activity_at": last_activity_at,
        "last_sick_increase_at": last_sick_increase_at,
        "first_cleared_at": first_cleared_at,
    }


def should_system_auto_close(
    case,
    *,
    now=None,
    lr_days: int = AUTO_CLOSE_LR_DAYS,
    mrhr_days: int = AUTO_CLOSE_MRHR_DAYS,
) -> bool:
    if getattr(case, "stopped_at", None) is not None or getattr(
        case, "is_finished", False
    ):
        return False
    clock = case_auto_close_clock(case)
    if clock is None:
        return False
    as_of = now or timezone.now()
    if clock["band"] == BAND_LR:
        last = clock["last_activity_at"]
        return last is not None and as_of - last >= timedelta(days=lr_days)

    mrhr = timedelta(days=mrhr_days)
    cleared_at = clock["first_cleared_at"]
    cleared = cleared_at is not None and as_of - cleared_at >= mrhr
    increase_at = clock["last_sick_increase_at"]
    plateau = increase_at is not None and as_of - increase_at >= mrhr
    return cleared or plateau
