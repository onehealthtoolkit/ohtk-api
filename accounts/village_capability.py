from accounts.models import Configuration


VILLAGE_CAPABILITY_KEY = "features.village_enabled"
FEATURE_ENABLED_VALUE = "enable"
FEATURE_DISABLED_VALUE = "disable"


def is_village_capability_enabled():
    return Configuration.objects.filter(
        key=VILLAGE_CAPABILITY_KEY, value=FEATURE_ENABLED_VALUE
    ).exists()


def set_village_capability_enabled(enabled):
    value = FEATURE_ENABLED_VALUE if enabled else FEATURE_DISABLED_VALUE
    configuration = Configuration._base_manager.filter(
        key=VILLAGE_CAPABILITY_KEY
    ).first()
    if configuration:
        configuration.value = value
        configuration.deleted_at = None
        configuration.save(update_fields=("value", "deleted_at", "updated_at"))
        return configuration

    configuration = Configuration.objects.create(
        key=VILLAGE_CAPABILITY_KEY,
        value=value,
    )
    return configuration
