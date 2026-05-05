import graphene
from django.db import transaction
from graphql import GraphQLError
from graphql_jwt.decorators import login_required

from accounts.animal_census_capability import is_animal_census_capability_enabled
from accounts.models import (
    AnimalCensusFact,
    AnimalSpecies,
    AuthorityUser,
    Village,
    VillageCensusSnapshot,
    VillageReporterAssignment,
)
from accounts.schema.types import (
    VillageCensusSnapshotProblem,
    VillageCensusSnapshotResult,
)
from accounts.village_capability import is_village_capability_enabled
from common.types import AdminFieldValidationProblem


class AnimalCensusFactInput(graphene.InputObjectType):
    species_id = graphene.Int(required=True)
    animal_quantity = graphene.Int(required=True)
    household_quantity = graphene.Int(required=True)


def validate_census_capabilities(problems):
    if not is_village_capability_enabled():
        problems.append(
            AdminFieldValidationProblem(
                name="village_enabled", message="village capability is not enabled"
            )
        )
    if not is_animal_census_capability_enabled():
        problems.append(
            AdminFieldValidationProblem(
                name="animal_census_enabled",
                message="animal census capability is not enabled",
            )
        )


def validate_official_assignment(user, village_id, problems):
    if not user.is_authority_role_in([AuthorityUser.Role.REPORTER]):
        problems.append(
            AdminFieldValidationProblem(
                name="reporter", message="only reporter users can submit census"
            )
        )
        return None

    assignment = VillageReporterAssignment.objects.filter(
        reporter=user.authorityuser,
        village_id=village_id,
        census_role=VillageReporterAssignment.CensusRole.OFFICIAL,
    ).first()
    if not assignment:
        problems.append(
            AdminFieldValidationProblem(
                name="village_id",
                message="official reporter assignment is required for village",
            )
        )
    return assignment


def validate_fact_inputs(facts, problems):
    active_species = list(AnimalSpecies.objects.filter(active=True))
    if not active_species:
        problems.append(
            AdminFieldValidationProblem(
                name="facts", message="at least one active species is required"
            )
        )
        return

    active_species_ids = {species.id for species in active_species}
    supplied_species_ids = [fact.species_id for fact in facts]
    supplied_species_id_set = set(supplied_species_ids)

    if len(supplied_species_ids) != len(supplied_species_id_set):
        problems.append(
            AdminFieldValidationProblem(
                name="facts", message="species can be submitted only once"
            )
        )

    missing_species_ids = active_species_ids - supplied_species_id_set
    if missing_species_ids:
        problems.append(
            AdminFieldValidationProblem(
                name="facts", message="all active species must be submitted"
            )
        )

    invalid_species_ids = supplied_species_id_set - active_species_ids
    if invalid_species_ids:
        problems.append(
            AdminFieldValidationProblem(
                name="facts", message="facts contain unknown or inactive species"
            )
        )

    for fact in facts:
        if fact.animal_quantity < 0 or fact.household_quantity < 0:
            problems.append(
                AdminFieldValidationProblem(
                    name="facts", message="quantities must be zero or greater"
                )
            )
            break


class SubmitVillageCensusSnapshotMutation(graphene.Mutation):
    class Arguments:
        village_id = graphene.Int(required=True)
        census_date = graphene.Date(required=True)
        facts = graphene.List(graphene.NonNull(AnimalCensusFactInput), required=True)

    result = graphene.Field(VillageCensusSnapshotResult)

    @staticmethod
    @login_required
    def mutate(root, info, village_id, census_date, facts):
        problems = []
        validate_census_capabilities(problems)

        try:
            Village.objects.get(pk=village_id)
        except Village.DoesNotExist:
            problems.append(
                AdminFieldValidationProblem(
                    name="village_id", message="village does not exist"
                )
            )

        user = info.context.user
        if not user.is_authority_user:
            raise GraphQLError("Permission denied.")

        validate_official_assignment(user, village_id, problems)
        validate_fact_inputs(facts, problems)

        if problems:
            return SubmitVillageCensusSnapshotMutation(
                result=VillageCensusSnapshotProblem(fields=problems)
            )

        with transaction.atomic():
            snapshot = VillageCensusSnapshot.objects.create(
                village_id=village_id,
                reporter=user.authorityuser,
                census_date=census_date,
            )
            AnimalCensusFact.objects.bulk_create(
                [
                    AnimalCensusFact(
                        snapshot=snapshot,
                        species_id=fact.species_id,
                        animal_quantity=fact.animal_quantity,
                        household_quantity=fact.household_quantity,
                    )
                    for fact in facts
                ]
            )

        return SubmitVillageCensusSnapshotMutation(result=snapshot)
