import graphene
from graphql import GraphQLError
from graphql_jwt.decorators import login_required

from accounts.models import AuthorityUser, Village, VillageReporterAssignment
from accounts.village_capability import is_village_capability_enabled
from census.animal_census_capability import is_animal_census_capability_enabled
from census.models import (
    AnimalSpecies,
    CensusDefinition,
    CensusDefinitionVersion,
    CurrentAnimalCensusFact,
    CurrentHumanCensusFact,
    VillageCensusSnapshot,
)
from census.schema.types import (
    AdminAnimalSpeciesQueryType,
    AnimalSpeciesType,
    CensusDefinitionType,
    CensusDefinitionVersionType,
    CensusKindSummaryType,
    CurrentAnimalCensusFactType,
    CurrentHumanCensusFactType,
    VillageCensusSnapshotType,
)
from pagination import DjangoPaginationConnectionField


class Query(graphene.ObjectType):
    admin_animal_species_query = DjangoPaginationConnectionField(
        AdminAnimalSpeciesQueryType
    )
    animal_species = graphene.List(AnimalSpeciesType)
    census_definitions = graphene.List(CensusDefinitionType)
    active_census_definition_version = graphene.Field(
        CensusDefinitionVersionType, kind=graphene.String(required=True)
    )
    active_village_census_definitions = graphene.List(
        CensusKindSummaryType, village_id=graphene.Int(required=True)
    )
    latest_village_census = graphene.Field(
        VillageCensusSnapshotType, village_id=graphene.Int(required=True)
    )
    latest_village_census_v2 = graphene.Field(
        VillageCensusSnapshotType,
        village_id=graphene.Int(required=True),
        kind=graphene.String(required=True),
    )
    current_animal_census_facts = graphene.List(
        CurrentAnimalCensusFactType, village_id=graphene.Int(required=True)
    )
    current_human_census_facts = graphene.List(
        CurrentHumanCensusFactType, village_id=graphene.Int(required=True)
    )
    animal_census_capability_enabled = graphene.Boolean(required=True)

    @staticmethod
    @login_required
    def resolve_animal_census_capability_enabled(root, info):
        return is_animal_census_capability_enabled()

    @staticmethod
    @login_required
    def resolve_admin_animal_species_query(root, info, **kwargs):
        user = info.context.user
        if not user.is_superuser:
            raise GraphQLError("Permission denied.")
        return AnimalSpecies.objects.all()

    @staticmethod
    @login_required
    def resolve_animal_species(root, info):
        if not (
            is_village_capability_enabled() and is_animal_census_capability_enabled()
        ):
            return AnimalSpecies.objects.none()
        return AnimalSpecies.objects.filter(active=True).order_by("sort_order", "code")

    @staticmethod
    @login_required
    def resolve_census_definitions(root, info):
        if not (
            is_village_capability_enabled() and is_animal_census_capability_enabled()
        ):
            return CensusDefinition.objects.none()
        return CensusDefinition.objects.filter(enabled=True).order_by(
            "sort_order", "kind"
        )

    @staticmethod
    @login_required
    def resolve_active_census_definition_version(root, info, kind):
        if not (
            is_village_capability_enabled() and is_animal_census_capability_enabled()
        ):
            return None
        return (
            CensusDefinitionVersion.objects.select_related("definition")
            .filter(
                definition__kind=kind,
                definition__enabled=True,
                status=CensusDefinitionVersion.Status.PUBLISHED,
            )
            .order_by("-version")
            .first()
        )

    @staticmethod
    @login_required
    def resolve_active_village_census_definitions(root, info, village_id):
        if not (
            is_village_capability_enabled() and is_animal_census_capability_enabled()
        ):
            return []

        village = _get_permitted_census_village(info, village_id)
        if village is None:
            return []

        definitions = CensusDefinition.objects.filter(enabled=True).order_by(
            "sort_order", "kind"
        )
        summaries = []
        for definition in definitions:
            active_version = (
                definition.versions.filter(
                    status=CensusDefinitionVersion.Status.PUBLISHED
                )
                .order_by("-version")
                .first()
            )
            if active_version is None:
                continue

            latest_snapshot = (
                VillageCensusSnapshot.objects.filter(
                    village=village, definition_version__definition=definition
                )
                .order_by("-census_date", "-created_at")
                .first()
            )
            summaries.append(
                CensusKindSummaryType(
                    kind=definition.kind,
                    name=_census_kind_name(definition.kind),
                    enabled=definition.enabled,
                    active_version=active_version,
                    latest_snapshot=latest_snapshot,
                )
            )
        return summaries

    @staticmethod
    @login_required
    def resolve_latest_village_census(root, info, village_id):
        if not (
            is_village_capability_enabled() and is_animal_census_capability_enabled()
        ):
            return None

        village = _get_permitted_census_village(info, village_id)
        if village is None:
            return None

        return (
            VillageCensusSnapshot.objects.filter(village=village)
            .order_by("-census_date", "-created_at")
            .first()
        )

    @staticmethod
    @login_required
    def resolve_latest_village_census_v2(root, info, village_id, kind):
        if not (
            is_village_capability_enabled() and is_animal_census_capability_enabled()
        ):
            return None

        village = _get_permitted_census_village(info, village_id)
        if village is None:
            return None

        return (
            VillageCensusSnapshot.objects.filter(
                village=village, definition_version__definition__kind=kind
            )
            .order_by("-census_date", "-created_at")
            .first()
        )

    @staticmethod
    @login_required
    def resolve_current_animal_census_facts(root, info, village_id):
        return CurrentAnimalCensusFact.objects.filter(
            fact__snapshot__village_id=village_id
        ).select_related("fact", "fact__animal_species")

    @staticmethod
    @login_required
    def resolve_current_human_census_facts(root, info, village_id):
        return CurrentHumanCensusFact.objects.filter(
            fact__snapshot__village_id=village_id
        ).select_related("fact")


def _get_permitted_census_village(info, village_id):
    user = info.context.user
    try:
        village = Village.objects.get(pk=village_id)
    except Village.DoesNotExist:
        return None

    if user.is_superuser:
        return village
    if user.is_authority_role_in([AuthorityUser.Role.ADMIN]):
        if user.authorityuser.authority.is_in_inherits_down([village.authority_id]):
            return village
        raise GraphQLError("Permission denied.")
    if user.is_authority_role_in([AuthorityUser.Role.OFFICER]):
        if user.authorityuser.authority_id == village.authority_id:
            return village
        raise GraphQLError("Permission denied.")
    if user.is_authority_role_in([AuthorityUser.Role.REPORTER]):
        if VillageReporterAssignment.objects.filter(
            reporter=user.authorityuser, village=village
        ).exists():
            return village
        raise GraphQLError("Permission denied.")
    raise GraphQLError("Permission denied.")


def _census_kind_name(kind):
    if kind == CensusDefinition.Kind.ANIMAL:
        return "Animal census"
    if kind == CensusDefinition.Kind.HUMAN:
        return "Human census"
    return f"{kind.title()} census"
