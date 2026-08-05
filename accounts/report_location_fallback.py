from accounts.models import Configuration


REPORT_USE_VILLAGE_LOCATION_FALLBACK_KEY = (
    "features.report_use_village_location_fallback"
)
FEATURE_ENABLED_VALUE = "enable"
FEATURE_DISABLED_VALUE = "disable"


def is_report_use_village_location_fallback_enabled():
    return Configuration.objects.filter(
        key=REPORT_USE_VILLAGE_LOCATION_FALLBACK_KEY,
        value=FEATURE_ENABLED_VALUE,
    ).exists()


def set_report_use_village_location_fallback_enabled(enabled):
    value = FEATURE_ENABLED_VALUE if enabled else FEATURE_DISABLED_VALUE
    configuration = Configuration._base_manager.filter(
        key=REPORT_USE_VILLAGE_LOCATION_FALLBACK_KEY
    ).first()
    if configuration:
        configuration.value = value
        configuration.deleted_at = None
        configuration.save(update_fields=("value", "deleted_at", "updated_at"))
        return configuration

    return Configuration.objects.create(
        key=REPORT_USE_VILLAGE_LOCATION_FALLBACK_KEY,
        value=value,
    )
