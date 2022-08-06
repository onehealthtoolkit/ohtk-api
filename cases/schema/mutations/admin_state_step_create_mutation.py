import graphene
from graphql_jwt.decorators import login_required, user_passes_test

from accounts.utils import is_superuser
from common.utils import is_duplicate, is_not_empty, check_and_get
from cases.models import StateDefinition, StateStep, StateStep
from cases.schema.types import (
    AdminStateStepCreateProblem,
    AdminStateStepCreateResult,
)


class AdminStateStepCreateMutation(graphene.Mutation):
    class Arguments:
        name = graphene.String(required=True)
        is_start_state = graphene.Boolean(required=None, default_value=True)
        is_stop_state = graphene.Boolean(required=None, default_value=True)
        state_definition_id = graphene.ID(required=True)

    result = graphene.Field(AdminStateStepCreateResult)

    @staticmethod
    @login_required
    @user_passes_test(is_superuser)
    def mutate(root, info, name, is_start_state, is_stop_state, state_definition_id):
        problems = []
        state_definition, problem = check_and_get(
            "state_definition_id", state_definition_id, StateDefinition
        )
        if problem:
            problems.append(problem)

        if name_problem := is_not_empty("name", name, "Name must not be empty"):
            problems.append(name_problem)

        if duplicateProblem := is_duplicate("name", name, StateStep):
            problems.append(duplicateProblem)

        if len(problems) > 0:
            return AdminStateStepCreateMutation(
                result=AdminStateStepCreateProblem(fields=problems)
            )

        state_step = StateStep.objects.create(
            name=name,
            is_start_state=is_start_state,
            is_stop_state=is_stop_state,
            state_definition=state_definition,
        )
        return AdminStateStepCreateMutation(result=state_step)
