from accounts.models import Configuration


REPORT_RESTRICT_TO_ASSIGNED_SCOPE_KEY = (
    "features.report_restrict_to_assigned_scope"
)
FEATURE_ENABLED_VALUE = "enable"
FEATURE_DISABLED_VALUE = "disable"


def is_report_restrict_to_assigned_scope_enabled():
    return Configuration.objects.filter(
        key=REPORT_RESTRICT_TO_ASSIGNED_SCOPE_KEY,
        value=FEATURE_ENABLED_VALUE,
    ).exists()


def set_report_restrict_to_assigned_scope_enabled(enabled):
    value = FEATURE_ENABLED_VALUE if enabled else FEATURE_DISABLED_VALUE
    configuration = Configuration._base_manager.filter(
        key=REPORT_RESTRICT_TO_ASSIGNED_SCOPE_KEY
    ).first()
    if configuration:
        configuration.value = value
        configuration.deleted_at = None
        configuration.save(update_fields=("value", "deleted_at", "updated_at"))
        return configuration

    return Configuration.objects.create(
        key=REPORT_RESTRICT_TO_ASSIGNED_SCOPE_KEY,
        value=value,
    )
