from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from census.definition_schema import generate_runtime_schema
from census.models import CensusDefinition, CensusDefinitionVersion


DEFAULT_ANIMAL_DEFINITION_SCHEMA = {
    "schema_version": 1,
    "dimensions": [
        {
            "key": "species",
            "label": {"default": "Species", "la": "ຊະນິດສັດ"},
            "values": [
                {"key": "CATTLE", "label": {"default": "Cattle", "la": "ງົວ"}},
                {"key": "BUFFALO", "label": {"default": "Buffalo", "la": "ຄວາຍ"}},
                {"key": "POULTRY", "label": {"default": "Poultry", "la": "ສັດປີກ"}},
            ],
        }
    ],
    "measures": [
        {
            "key": "animal_quantity",
            "label": {"default": "Animal quantity", "la": "ຈຳນວນສັດ"},
            "type": "integer",
            "required": True,
        },
        {
            "key": "household_quantity",
            "label": {"default": "Households", "la": "ຄົວເຮືອນ"},
            "type": "integer",
            "required": True,
        },
    ],
}


DEFAULT_HUMAN_DEFINITION_SCHEMA = {
    "schema_version": 1,
    "display": {
        "single_row_label": {"default": "Total", "la": "ລວມ"},
    },
    "dimensions": [],
    "measures": [
        {
            "key": "population",
            "label": {"default": "Population", "la": "ປະຊາກອນ"},
            "type": "integer",
            "required": True,
        }
    ],
}


def default_schema_for_kind(kind):
    if kind == CensusDefinition.Kind.ANIMAL:
        return generate_runtime_schema(DEFAULT_ANIMAL_DEFINITION_SCHEMA)
    if kind == CensusDefinition.Kind.HUMAN:
        return generate_runtime_schema(DEFAULT_HUMAN_DEFINITION_SCHEMA)
    raise ValueError("unsupported census definition kind")


def default_definition_schema_for_kind(kind):
    if kind == CensusDefinition.Kind.ANIMAL:
        return DEFAULT_ANIMAL_DEFINITION_SCHEMA
    if kind == CensusDefinition.Kind.HUMAN:
        return DEFAULT_HUMAN_DEFINITION_SCHEMA
    raise ValueError("unsupported census definition kind")


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


def publish_schema_version(definition, schema, definition_schema=None):
    with transaction.atomic():
        definition.versions.filter(
            status=CensusDefinitionVersion.Status.PUBLISHED
        ).update(status=CensusDefinitionVersion.Status.RETIRED)
        draft = (
            definition.versions.filter(status=CensusDefinitionVersion.Status.DRAFT)
            .order_by("-version")
            .first()
        )
        if draft:
            draft.schema = schema
            draft.definition_schema = definition_schema
            draft.status = CensusDefinitionVersion.Status.PUBLISHED
            draft.published_at = timezone.now()
            draft.save(
                update_fields=[
                    "schema",
                    "definition_schema",
                    "status",
                    "published_at",
                    "updated_at",
                ]
            )
            return draft
        return CensusDefinitionVersion.objects.create(
            definition=definition,
            version=next_version_number(definition),
            status=CensusDefinitionVersion.Status.PUBLISHED,
            schema=schema,
            definition_schema=definition_schema,
            published_at=timezone.now(),
        )


def save_schema_draft(definition, schema, definition_schema=None):
    with transaction.atomic():
        draft = (
            definition.versions.filter(status=CensusDefinitionVersion.Status.DRAFT)
            .order_by("-version")
            .first()
        )
        if draft:
            draft.schema = schema
            draft.definition_schema = definition_schema
            draft.save(
                update_fields=[
                    "schema",
                    "definition_schema",
                    "updated_at",
                ]
            )
            return draft
        return CensusDefinitionVersion.objects.create(
            definition=definition,
            version=next_version_number(definition),
            status=CensusDefinitionVersion.Status.DRAFT,
            schema=schema,
            definition_schema=definition_schema,
        )


def ensure_published_schema(definition, schema, reset_schema=False):
    current = definition.versions.filter(
        status=CensusDefinitionVersion.Status.PUBLISHED
    ).first()
    if current and not reset_schema:
        return current
    definition_schema = default_definition_schema_for_kind(definition.kind)
    return publish_schema_version(definition, schema, definition_schema)


def ensure_default_census_setup(seed_species=True, reset_schema=False):
    animal = ensure_definition(CensusDefinition.Kind.ANIMAL, enabled=True, sort_order=1)
    human = ensure_definition(CensusDefinition.Kind.HUMAN, enabled=True, sort_order=2)
    animal_version = ensure_published_schema(
        animal,
        default_schema_for_kind(CensusDefinition.Kind.ANIMAL),
        reset_schema=reset_schema,
    )
    human_version = ensure_published_schema(
        human,
        default_schema_for_kind(CensusDefinition.Kind.HUMAN),
        reset_schema=reset_schema,
    )
    return [animal, human], [animal_version, human_version]
