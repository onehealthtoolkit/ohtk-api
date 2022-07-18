import graphene
from graphql_jwt.decorators import login_required
from graphene.types.generic import GenericScalar

from cases.models import Case, StateTransition
from cases.schema.types import CaseStateType


class ForwardStateMutation(graphene.Mutation):
    class Arguments:
        case_id = graphene.ID(required=True)
        from_case_state_id = graphene.ID(required=True)
        transition_id = graphene.ID(required=True)
        form_data = GenericScalar(required=False)

    result = graphene.Field(CaseStateType)

    @staticmethod
    @login_required
    def mutate(root, info, case_id, from_case_state_id, transition_id, form_data):
        user = info.context.user
        case = Case.objects.get(pk=case_id)
        case_state = case.current_states.get(id=from_case_state_id)
        transition = StateTransition.objects.get(pk=transition_id)
        assert transition.from_step.id == case_state.state.id
        next_state = case.forward_state(
            from_step_id=case_state.state.id,
            to_step_id=transition.to_step_id,
            form_data=form_data,
            created_by=user,
        )
        return {"result": next_state}
