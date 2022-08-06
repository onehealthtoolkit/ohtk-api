import json
import graphene
from graphql_jwt.decorators import login_required, user_passes_test

from accounts.utils import is_superuser
from common.utils import is_duplicate, is_not_empty, check_and_get
from cases.models import StateDefinition, StateStep, StateTransition
from cases.schema.types import (
    AdminStateTransitionUpdateProblem,
    AdminStateTransitionUpdateResult,
    AdminStateTransitionUpdateSuccess,
)


class AdminStateTransitionUpdateMutation(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)
        from_step_id = graphene.ID(required=True)
        to_step_id = graphene.ID(required=True)
        form_definition = graphene.String(required=True)

    result = graphene.Field(AdminStateTransitionUpdateResult)

    @staticmethod
    @login_required
    @user_passes_test(is_superuser)
    def mutate(root, info, id, from_step_id, to_step_id, form_definition):
        try:
            state_transition = StateTransition.objects.get(pk=id)
        except StateTransition.DoesNotExist:
            return AdminStateTransitionUpdateMutation(
                result=AdminStateTransitionUpdateProblem(
                    fields=[], message="Object not found"
                )
            )

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
            return AdminStateTransitionUpdateMutation(
                result=AdminStateTransitionUpdateProblem(fields=problems)
            )

        state_transition.from_step = from_step
        state_transition.to_step = to_step
        state_transition.form_definition = json.loads(form_definition)
        state_transition.save()
        return AdminStateTransitionUpdateMutation(
            result=AdminStateTransitionUpdateSuccess(state_transition=state_transition)
        )
