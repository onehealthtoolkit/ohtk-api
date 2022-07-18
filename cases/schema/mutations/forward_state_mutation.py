import graphene
from graphql_jwt.decorators import login_required
from graphene.types.generic import GenericScalar

from cases.models import Case, StateTransition
from cases.schema.types import CaseStateType


class ForwardStateMutation(graphene.Mutation):
    class Arguments:
        case_id = graphene.ID(required=True)
        transition_id = graphene.ID(required=True)
        form_data = GenericScalar(required=False)

    result = graphene.Field(CaseStateType)

    @staticmethod
    @login_required
    def mutate(root, info, case_id, transition_id, form_data):
        user = info.context.user
        case = Case.objects.get(pk=case_id)
        transition = StateTransition.objects.get(pk=transition_id)
        next_state = case.forward_state(
            from_step_id=transition.from_step.id,
            to_step_id=transition.to_step_id,
            form_data=form_data,
            created_by=user,
        )
        return {"result": next_state}
