import json
import graphene
from common.utils import is_not_empty, check_and_get
from cases.models import StateStep, StateTransition, StateTransition
from cases.schema.types import (
    AdminStateTransitionCreateProblem,
    AdminStateTransitionCreateResult,
)


class AdminStateTransitionCreateMutation(graphene.Mutation):
    class Arguments:
        from_step_id = graphene.ID(required=True)
        to_step_id = graphene.ID(required=True)
        form_definition = graphene.String(required=True)

    result = graphene.Field(AdminStateTransitionCreateResult)

    @staticmethod
    def mutate(root, info, from_step_id, to_step_id, form_definition):
        problems = []
        from_step, from_step_problem = check_and_get(
            "from_step_id", from_step_id, StateStep
        )
        if from_step_problem:
            problems.append(from_step_problem)

        to_step, to_step_problem = check_and_get("to_step_id", to_step_id, StateStep)
        if to_step_problem:
            problems.append(to_step_problem)

        if form_definition_problem := is_not_empty(
            "form_definition", form_definition, "Form definition must not be empty"
        ):
            problems.append(form_definition_problem)

        if len(problems) > 0:
            return AdminStateTransitionCreateMutation(
                result=AdminStateTransitionCreateProblem(fields=problems)
            )

        state_transition = StateTransition.objects.create(
            from_step=from_step,
            to_step=to_step,
            form_definition=json.loads(form_definition),
        )
        return AdminStateTransitionCreateMutation(result=state_transition)
