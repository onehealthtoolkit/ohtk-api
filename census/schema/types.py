import django_filters
import graphene
from django.db.models import Q
from graphene.types.generic import GenericScalar
from graphene_django import DjangoObjectType

from census.models import (
    AnimalCensusFact,
    AnimalSpecies,
    CensusDefinition,
    CensusDefinitionVersion,
    CurrentAnimalCensusFact,
    CurrentHumanCensusFact,
    HumanCensusFact,
    VillageCensusSnapshot,
)
from common.types import AdminFieldValidationProblem, AdminValidationProblem


class AdminAnimalSpeciesQueryFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(method="filter_q")
    active = django_filters.BooleanFilter()

    class Meta:
        model = AnimalSpecies
        fields = ["active"]

    def filter_q(self, queryset, name, value):
        return queryset.filter(Q(name__icontains=value) | Q(code__icontains=value))


class AnimalSpeciesType(DjangoObjectType):
    class Meta:
        model = AnimalSpecies
        fields = ("id", "code", "name", "active", "sort_order")


class AdminAnimalSpeciesQueryType(DjangoObjectType):
    class Meta:
        model = AnimalSpecies
        fields = ("id", "code", "name", "active", "sort_order")
        filterset_class = AdminAnimalSpeciesQueryFilter


class AdminAnimalSpeciesCreateSuccess(DjangoObjectType):
    class Meta:
        model = AnimalSpecies
        fields = "__all__"


class AdminAnimalSpeciesCreateProblem(AdminValidationProblem):
    pass


class AdminAnimalSpeciesCreateResult(graphene.Union):
    class Meta:
        types = (AdminAnimalSpeciesCreateSuccess, AdminAnimalSpeciesCreateProblem)


class AdminAnimalSpeciesUpdateSuccess(DjangoObjectType):
    class Meta:
        model = AnimalSpecies
        fields = "__all__"


class AdminAnimalSpeciesUpdateProblem(AdminValidationProblem):
    pass


class AdminAnimalSpeciesUpdateResult(graphene.Union):
    class Meta:
        types = (AdminAnimalSpeciesUpdateSuccess, AdminAnimalSpeciesUpdateProblem)


class AnimalCensusFactType(DjangoObjectType):
    species = graphene.Field(AnimalSpeciesType)
    animal_quantity = graphene.Int()
    household_quantity = graphene.Int()
    extra_dimensions = GenericScalar()
    measures = GenericScalar()

    class Meta:
        model = AnimalCensusFact
        fields = (
            "id",
            "animal_species",
            "row_key",
            "extra_dimensions",
            "measures",
        )

    def resolve_species(self, info):
        return self.animal_species

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
    runtime_schema = GenericScalar()

    class Meta:
        model = CensusDefinitionVersion
        fields = (
            "id",
            "definition",
            "version",
            "status",
            "schema",
            "published_at",
        )

    def resolve_runtime_schema(self, info):
        schema = dict(self.schema or {})
        if self.definition.kind == CensusDefinition.Kind.ANIMAL:
            schema["rows"] = [
                {
                    "species_id": species.id,
                    "species_code": species.code,
                    "label": species.name,
                    "row_key": f"species:{species.code}",
                }
                for species in AnimalSpecies.objects.filter(active=True).order_by(
                    "sort_order", "code"
                )
            ]
        return schema


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
