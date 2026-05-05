from accounts.models import Configuration


VILLAGE_CAPABILITY_KEY = "features.village_enabled"
FEATURE_ENABLED_VALUE = "enable"
FEATURE_DISABLED_VALUE = "disable"


def is_village_capability_enabled():
    return Configuration.objects.filter(
        key=VILLAGE_CAPABILITY_KEY, value=FEATURE_ENABLED_VALUE
    ).exists()


def set_village_capability_enabled(enabled):
    configuration, _ = Configuration.objects.update_or_create(
        key=VILLAGE_CAPABILITY_KEY,
        defaults={
            "value": FEATURE_ENABLED_VALUE if enabled else FEATURE_DISABLED_VALUE
        },
    )
    return configuration
