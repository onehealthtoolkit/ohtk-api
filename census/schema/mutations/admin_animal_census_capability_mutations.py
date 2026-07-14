import graphene
from graphql_jwt.decorators import login_required, superuser_required

from census.animal_census_capability import set_animal_census_capability_enabled
from common.types import AdminFieldValidationProblem


class AdminAnimalCensusCapabilityUpdateMutation(graphene.Mutation):
    class Arguments:
        enabled = graphene.Boolean(required=True)

    enabled = graphene.Boolean(required=False)
    fields = graphene.List(AdminFieldValidationProblem)

    @staticmethod
    @login_required
    @superuser_required
    def mutate(root, info, enabled):
        try:
            set_animal_census_capability_enabled(enabled)
        except ValueError as error:
            return AdminAnimalCensusCapabilityUpdateMutation(
                enabled=False,
                fields=[
                    AdminFieldValidationProblem(
                        name="animal_census_enabled", message=str(error)
                    )
                ],
            )
        return AdminAnimalCensusCapabilityUpdateMutation(enabled=enabled, fields=[])
