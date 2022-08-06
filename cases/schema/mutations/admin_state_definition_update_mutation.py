import graphene
from graphql_jwt.decorators import login_required, user_passes_test

from accounts.utils import is_superuser
from common.utils import is_duplicate, is_not_empty, check_and_get
from cases.models import StateDefinition
from cases.schema.types import (
    AdminStateDefinitionUpdateProblem,
    AdminStateDefinitionUpdateResult,
    AdminStateDefinitionUpdateSuccess,
)


class AdminStateDefinitionUpdateMutation(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)
        name = graphene.String(required=True)
        is_default = graphene.Boolean(required=None, default_value=True)

    result = graphene.Field(AdminStateDefinitionUpdateResult)

    @staticmethod
    @login_required
    @user_passes_test(is_superuser)
    def mutate(root, info, id, name, is_default):
        print(id)
        try:
            state_definition = StateDefinition.objects.get(pk=id)
        except StateDefinition.DoesNotExist:
            return AdminStateDefinitionUpdateMutation(
                result=AdminStateDefinitionUpdateProblem(
                    fields=[], message="Object not found"
                )
            )

        problems = []
        if name_problem := is_not_empty("name", name, "Name must not be empty"):
            problems.append(name_problem)

        if state_definition.name != name:
            if duplicateProblem := is_duplicate("name", name, StateDefinition):
                problems.append(duplicateProblem)

        if len(problems) > 0:
            return AdminStateDefinitionUpdateMutation(
                result=AdminStateDefinitionUpdateProblem(fields=problems)
            )

        state_definition.name = name
        state_definition.is_default = is_default
        state_definition.save()
        return AdminStateDefinitionUpdateMutation(
            result=AdminStateDefinitionUpdateSuccess(state_definition=state_definition)
        )
