import graphene
from common.utils import is_duplicate, is_not_empty, check_and_get
from cases.models import StateDefinition, StateStep
from cases.schema.types import (
    AdminStateStepUpdateProblem,
    AdminStateStepUpdateResult,
    AdminStateStepUpdateSuccess,
)


class AdminStateStepUpdateMutation(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)
        name = graphene.String(required=True)
        is_start_state = graphene.Boolean(required=None, default_value=True)
        is_stop_state = graphene.Boolean(required=None, default_value=True)
        state_definition_id = graphene.ID(required=True)

    result = graphene.Field(AdminStateStepUpdateResult)

    @staticmethod
    def mutate(
        root, info, id, name, is_start_state, is_stop_state, state_definition_id
    ):
        try:
            state_step = StateStep.objects.get(pk=id)
        except StateStep.DoesNotExist:
            return AdminStateStepUpdateMutation(
                result=AdminStateStepUpdateProblem(
                    fields=[], message="Object not found"
                )
            )

        problems = []
        state_definition, problem = check_and_get(
            "state_definition_id", state_definition_id, StateDefinition
        )
        if problem:
            problems.append(problem)
        if name_problem := is_not_empty("name", name, "Name must not be empty"):
            problems.append(name_problem)

        if state_step.name != name:
            if duplicateProblem := is_duplicate("name", name, StateStep):
                problems.append(duplicateProblem)

        if len(problems) > 0:
            return AdminStateStepUpdateMutation(
                result=AdminStateStepUpdateProblem(fields=problems)
            )

        state_step.name = name
        state_step.is_start_state = is_start_state
        state_step.is_stop_state = is_stop_state
        state_step.state_definition = state_definition
        state_step.save()
        return AdminStateStepUpdateMutation(
            result=AdminStateStepUpdateSuccess(state_step=state_step)
        )
