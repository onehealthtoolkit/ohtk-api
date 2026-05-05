import graphene
from graphql_jwt.decorators import login_required, superuser_required

from accounts.models import AnimalSpecies
from accounts.schema.types import (
    AdminAnimalSpeciesCreateProblem,
    AdminAnimalSpeciesCreateResult,
    AdminAnimalSpeciesUpdateProblem,
    AdminAnimalSpeciesUpdateResult,
)
from common.types import AdminFieldValidationProblem
from common.utils import is_not_empty


def validate_species_code(code, problems, existing_id=None):
    if code_problem := is_not_empty("code", code, "Code must not be empty"):
        problems.append(code_problem)

    query = AnimalSpecies.objects.filter(code=code)
    if existing_id is not None:
        query = query.exclude(pk=existing_id)
    if query.exists():
        problems.append(
            AdminFieldValidationProblem(name="code", message="duplicate code")
        )


class AdminAnimalSpeciesCreateMutation(graphene.Mutation):
    class Arguments:
        code = graphene.String(required=True)
        name = graphene.String(required=True)
        active = graphene.Boolean(required=False, default_value=True)
        sort_order = graphene.Int(required=False, default_value=0)

    result = graphene.Field(AdminAnimalSpeciesCreateResult)

    @staticmethod
    @login_required
    @superuser_required
    def mutate(root, info, code, name, active=True, sort_order=0):
        problems = []
        validate_species_code(code, problems)
        if name_problem := is_not_empty("name", name, "Name must not be empty"):
            problems.append(name_problem)

        if problems:
            return AdminAnimalSpeciesCreateMutation(
                result=AdminAnimalSpeciesCreateProblem(fields=problems)
            )

        species = AnimalSpecies.objects.create(
            code=code, name=name, active=active, sort_order=sort_order
        )
        return AdminAnimalSpeciesCreateMutation(result=species)


class AdminAnimalSpeciesUpdateMutation(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)
        code = graphene.String(required=True)
        name = graphene.String(required=True)
        active = graphene.Boolean(required=True)
        sort_order = graphene.Int(required=False, default_value=0)

    result = graphene.Field(AdminAnimalSpeciesUpdateResult)

    @staticmethod
    @login_required
    @superuser_required
    def mutate(root, info, id, code, name, active, sort_order=0):
        try:
            species = AnimalSpecies.objects.get(pk=id)
        except AnimalSpecies.DoesNotExist:
            return AdminAnimalSpeciesUpdateMutation(
                result=AdminAnimalSpeciesUpdateProblem(
                    fields=[], message="species does not exist"
                )
            )

        problems = []
        validate_species_code(code, problems, existing_id=id)
        if name_problem := is_not_empty("name", name, "Name must not be empty"):
            problems.append(name_problem)

        if problems:
            return AdminAnimalSpeciesUpdateMutation(
                result=AdminAnimalSpeciesUpdateProblem(fields=problems)
            )

        species.code = code
        species.name = name
        species.active = active
        species.sort_order = sort_order
        species.save()
        return AdminAnimalSpeciesUpdateMutation(result=species)
