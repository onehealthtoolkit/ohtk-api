import graphene
from graphene.types.generic import GenericScalar
from graphene_django import DjangoObjectType

from accounts.schema.types import VillageType
from census.definition_schema import runtime_schema_for_version
from census.models import (
    AnimalCensusFact,
    CensusDefinition,
    CensusDefinitionVersion,
    CensusRoundDefinition,
    CensusRoundOccurrence,
    CurrentAnimalCensusFact,
    CurrentHumanCensusFact,
    HumanCensusFact,
    VillageCensusSnapshot,
)
from common.types import AdminFieldValidationProblem, AdminValidationProblem


class AnimalCensusFactType(DjangoObjectType):
    animal_quantity = graphene.Int()
    household_quantity = graphene.Int()
    extra_dimensions = GenericScalar()
    measures = GenericScalar()

    class Meta:
        model = AnimalCensusFact
        fields = (
            "id",
            "row_key",
            "row_label",
            "extra_dimensions",
            "measures",
        )

    def resolve_animal_quantity(self, info):
        return self.measures.get("animal_quantity", 0)

    def resolve_household_quantity(self, info):
        return self.measures.get("household_quantity", 0)


class CensusDefinitionType(DjangoObjectType):
    class Meta:
        model = CensusDefinition
        fields = ("id", "kind", "enabled", "sort_order")


class CensusDefinitionVersionType(DjangoObjectType):
    schema = GenericScalar()
    definition_schema = GenericScalar()
    runtime_schema = GenericScalar()

    class Meta:
        model = CensusDefinitionVersion
        fields = (
            "id",
            "definition",
            "version",
            "status",
            "schema",
            "definition_schema",
            "published_at",
        )

    def resolve_runtime_schema(self, info):
        return runtime_schema_for_version(self)


class CensusRoundDefinitionType(DjangoObjectType):
    class Meta:
        model = CensusRoundDefinition
        fields = (
            "id",
            "code",
            "name",
            "kind",
            "mode",
            "repeat",
            "census_period_start",
            "census_period_end",
            "start_date",
            "soft_finish_date",
            "hard_finish_date",
            "target_authority",
            "enabled",
        )


class CensusRoundOccurrenceType(DjangoObjectType):
    status = graphene.String(required=True)

    class Meta:
        model = CensusRoundOccurrence
        fields = (
            "id",
            "definition",
            "year",
            "occurrence_key",
            "kind",
            "mode",
            "census_period_start",
            "census_period_end",
            "start_date",
            "soft_finish_date",
            "hard_finish_date",
            "target_authority",
        )

    def resolve_status(self, info):
        return self.status


class HumanCensusFactType(DjangoObjectType):
    dimensions = GenericScalar()
    measures = GenericScalar()

    class Meta:
        model = HumanCensusFact
        fields = ("id", "row_key", "dimensions", "measures")


class CurrentAnimalCensusFactType(DjangoObjectType):
    class Meta:
        model = CurrentAnimalCensusFact
        fields = ("id", "fact", "updated_at")


class CurrentHumanCensusFactType(DjangoObjectType):
    class Meta:
        model = CurrentHumanCensusFact
        fields = ("id", "fact", "updated_at")


class AdminCensusDefinitionSetupPayload(graphene.ObjectType):
    definitions = graphene.List(CensusDefinitionType)
    versions = graphene.List(CensusDefinitionVersionType)
    fields = graphene.List(AdminFieldValidationProblem)


class AdminCensusDefinitionVersionPublishPayload(graphene.ObjectType):
    definition = graphene.Field(CensusDefinitionType)
    version = graphene.Field(CensusDefinitionVersionType)
    fields = graphene.List(AdminFieldValidationProblem)


class AdminCensusDefinitionSetEnabledPayload(graphene.ObjectType):
    definition = graphene.Field(CensusDefinitionType)
    version = graphene.Field(CensusDefinitionVersionType)
    fields = graphene.List(AdminFieldValidationProblem)


class AdminCensusRoundDefinitionSavePayload(graphene.ObjectType):
    definition = graphene.Field(CensusRoundDefinitionType)
    occurrences = graphene.List(CensusRoundOccurrenceType)
    fields = graphene.List(AdminFieldValidationProblem)


class VillageCensusSnapshotType(DjangoObjectType):
    form_data = GenericScalar()
    village_household_quantity = graphene.Int()
    animal_household_quantity = graphene.Int()

    class Meta:
        model = VillageCensusSnapshot
        fields = (
            "id",
            "village",
            "reporter",
            "definition_version",
            "round_occurrence",
            "round_resolution",
            "census_date",
            "form_data",
            "status",
            "submitted_at",
            "facts",
            "human_facts",
        )

    def resolve_village_household_quantity(self, info):
        return _summary_quantity(self, "village_household_quantity")

    def resolve_animal_household_quantity(self, info):
        return _summary_quantity(self, "animal_household_quantity")


def _summary_quantity(snapshot, key):
    if snapshot is None:
        return None
    summary = (snapshot.form_data or {}).get("summary")
    if not isinstance(summary, dict):
        return None
    value = summary.get(key)
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class VillageCensusSnapshotProblem(AdminValidationProblem):
    pass


class VillageCensusSnapshotResult(graphene.Union):
    class Meta:
        types = (VillageCensusSnapshotType, VillageCensusSnapshotProblem)


class CensusKindSummaryType(graphene.ObjectType):
    kind = graphene.String(required=True)
    name = graphene.String(required=True)
    enabled = graphene.Boolean(required=True)
    active_version = graphene.Field(CensusDefinitionVersionType)
    latest_snapshot = graphene.Field(VillageCensusSnapshotType)


class CensusRoundCoverageRowType(graphene.ObjectType):
    village = graphene.Field(VillageType, required=True)
    occurrence = graphene.Field(CensusRoundOccurrenceType, required=True)
    status = graphene.String(required=True)
    snapshot = graphene.Field(VillageCensusSnapshotType)
    village_household_quantity = graphene.Int()
    animal_household_quantity = graphene.Int()
    total_animal_quantity = graphene.Int()
    species_summary = GenericScalar()

    def resolve_village(self, info):
        return self["village"]

    def resolve_occurrence(self, info):
        return self["occurrence"]

    def resolve_status(self, info):
        return self["status"]

    def resolve_snapshot(self, info):
        return self["snapshot"]

    def resolve_village_household_quantity(self, info):
        snapshot = self["snapshot"]
        return _summary_quantity(snapshot, "village_household_quantity")

    def resolve_animal_household_quantity(self, info):
        snapshot = self["snapshot"]
        return _summary_quantity(snapshot, "animal_household_quantity")

    def resolve_total_animal_quantity(self, info):
        return self["total_animal_quantity"]

    def resolve_species_summary(self, info):
        return self["species_summary"]


class CensusRoundCoverageType(graphene.ObjectType):
    total_count = graphene.Int(required=True)
    submitted_count = graphene.Int(required=True)
    missing_count = graphene.Int(required=True)
    late_count = graphene.Int(required=True)
    rows = graphene.List(CensusRoundCoverageRowType, required=True)
