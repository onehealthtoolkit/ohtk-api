from accounts.models import Configuration
from accounts.village_capability import (
    FEATURE_DISABLED_VALUE,
    FEATURE_ENABLED_VALUE,
    is_village_capability_enabled,
)


ANIMAL_CENSUS_CAPABILITY_KEY = "features.animal_census_enabled"


def is_animal_census_capability_enabled():
    return Configuration.objects.filter(
        key=ANIMAL_CENSUS_CAPABILITY_KEY, value=FEATURE_ENABLED_VALUE
    ).exists()


def set_animal_census_capability_enabled(enabled):
    if enabled and not is_village_capability_enabled():
        raise ValueError("animal census capability requires village capability")

    value = FEATURE_ENABLED_VALUE if enabled else FEATURE_DISABLED_VALUE
    configuration = Configuration._base_manager.filter(
        key=ANIMAL_CENSUS_CAPABILITY_KEY
    ).first()
    if configuration:
        configuration.value = value
        configuration.deleted_at = None
        configuration.save(update_fields=("value", "deleted_at", "updated_at"))
        return configuration

    return Configuration.objects.create(
        key=ANIMAL_CENSUS_CAPABILITY_KEY,
        value=value,
    )
