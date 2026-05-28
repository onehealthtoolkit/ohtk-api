import graphene
from graphene.types.generic import GenericScalar
from graphene_django import DjangoObjectType

from census.definition_schema import runtime_schema_for_version
from census.models import (
    AnimalCensusFact,
    CensusDefinition,
    CensusDefinitionVersion,
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


class VillageCensusSnapshotType(DjangoObjectType):
    form_data = GenericScalar()

    class Meta:
        model = VillageCensusSnapshot
        fields = (
            "id",
            "village",
            "reporter",
            "definition_version",
            "census_date",
            "form_data",
            "status",
            "submitted_at",
            "facts",
            "human_facts",
        )


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
