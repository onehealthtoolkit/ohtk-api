from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from census.models import AnimalSpecies, CensusDefinition, CensusDefinitionVersion


DEFAULT_ANIMAL_SCHEMA = {
    "row_source": "ACTIVE_ANIMAL_SPECIES",
    "measures": [
        {
            "key": "animal_quantity",
            "label": "Animal quantity",
            "type": "integer",
            "required": True,
        },
        {
            "key": "household_quantity",
            "label": "Households",
            "type": "integer",
            "required": True,
        },
    ],
    "extra_dimensions": [],
}

DEFAULT_HUMAN_SCHEMA = {
    "rows": [
        {
            "key": "total",
            "label": "Total",
            "dimensions": {},
        },
    ],
    "measures": [
        {
            "key": "population",
            "label": "Population",
            "type": "integer",
            "required": True,
        }
    ],
}

DEFAULT_SPECIES = [
    {"code": "CATTLE", "name": "Cattle", "sort_order": 1},
    {"code": "BUFFALO", "name": "Buffalo", "sort_order": 2},
    {"code": "POULTRY", "name": "Poultry", "sort_order": 3},
]


def default_schema_for_kind(kind):
    if kind == CensusDefinition.Kind.ANIMAL:
        return DEFAULT_ANIMAL_SCHEMA
    if kind == CensusDefinition.Kind.HUMAN:
        return DEFAULT_HUMAN_SCHEMA
    raise ValueError("unsupported census definition kind")


def ensure_default_species():
    species = []
    for item in DEFAULT_SPECIES:
        species_item, _created = AnimalSpecies.objects.get_or_create(
            code=item["code"],
            defaults={
                "name": item["name"],
                "active": True,
                "sort_order": item["sort_order"],
            },
        )
        species.append(species_item)
    return species


def ensure_definition(kind, enabled=True, sort_order=0):
    definition, _created = CensusDefinition.objects.get_or_create(
        kind=kind,
        defaults={"enabled": enabled, "sort_order": sort_order},
    )
    changed = False
    if definition.enabled != enabled:
        definition.enabled = enabled
        changed = True
    if definition.sort_order != sort_order:
        definition.sort_order = sort_order
        changed = True
    if changed:
        definition.save(update_fields=["enabled", "sort_order", "updated_at"])
    return definition


def next_version_number(definition):
    value = definition.versions.aggregate(max_version=Max("version"))["max_version"]
    return (value or 0) + 1


def publish_schema_version(definition, schema):
    with transaction.atomic():
        definition.versions.filter(
            status=CensusDefinitionVersion.Status.PUBLISHED
        ).update(status=CensusDefinitionVersion.Status.RETIRED)
        return CensusDefinitionVersion.objects.create(
            definition=definition,
            version=next_version_number(definition),
            status=CensusDefinitionVersion.Status.PUBLISHED,
            schema=schema,
            published_at=timezone.now(),
        )


def ensure_published_schema(definition, schema, reset_schema=False):
    current = definition.versions.filter(
        status=CensusDefinitionVersion.Status.PUBLISHED
    ).first()
    if current and not reset_schema:
        return current
    return publish_schema_version(definition, schema)


def ensure_default_census_setup(seed_species=True, reset_schema=False):
    if seed_species:
        ensure_default_species()

    animal = ensure_definition(CensusDefinition.Kind.ANIMAL, enabled=True, sort_order=1)
    human = ensure_definition(CensusDefinition.Kind.HUMAN, enabled=True, sort_order=2)
    animal_version = ensure_published_schema(
        animal, DEFAULT_ANIMAL_SCHEMA, reset_schema=reset_schema
    )
    human_version = ensure_published_schema(
        human, DEFAULT_HUMAN_SCHEMA, reset_schema=reset_schema
    )
    return [animal, human], [animal_version, human_version]
