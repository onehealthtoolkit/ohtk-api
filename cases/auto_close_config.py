"""Tenant Configuration for the legacy single CO3 window.

D07 auto-close does **not** use this key. It is kept for admin/ops display
and tests of Configuration.get. The job windows are 14 (LOW) and 21 (MR/HR).
"""

from django.conf import settings

from accounts.models import Configuration

CASE_AUTO_CLOSE_DAYS_KEY = "cases.auto_close_days"
DEFAULT_CASE_AUTO_CLOSE_DAYS = 21


def get_default_case_auto_close_days() -> int:
    """Global fallback when DB config missing/invalid (settings then 21)."""
    raw = getattr(settings, "CASE_AUTO_CLOSE_DAYS", None)
    if raw is None or raw == "":
        return DEFAULT_CASE_AUTO_CLOSE_DAYS
    try:
        days = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_CASE_AUTO_CLOSE_DAYS
    if days < 1:
        return DEFAULT_CASE_AUTO_CLOSE_DAYS
    return days


def get_case_auto_close_days() -> int:
    """
    Resolve auto-close window for the **current** tenant schema.

    Order:
    1. Configuration.cases.auto_close_days (if valid int >= 1)
    2. settings.CASE_AUTO_CLOSE_DAYS
    3. 21
    """
    raw = Configuration.get(CASE_AUTO_CLOSE_DAYS_KEY)
    if raw is not None and str(raw).strip() != "":
        try:
            days = int(str(raw).strip())
            if days >= 1:
                return days
        except (TypeError, ValueError):
            pass
    return get_default_case_auto_close_days()


def set_case_auto_close_days(days: int) -> Configuration:
    """Upsert tenant Configuration for CO3 days. Raises ValueError if days < 1."""
    if days is None or int(days) < 1:
        raise ValueError("case auto close days must be >= 1")
    days = int(days)
    value = str(days)
    configuration = Configuration._base_manager.filter(
        key=CASE_AUTO_CLOSE_DAYS_KEY
    ).first()
    if configuration:
        configuration.value = value
        configuration.deleted_at = None
        configuration.save(update_fields=("value", "deleted_at", "updated_at"))
        return configuration
    return Configuration.objects.create(key=CASE_AUTO_CLOSE_DAYS_KEY, value=value)
