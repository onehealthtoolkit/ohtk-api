import graphene
from graphql_jwt.decorators import login_required, superuser_required

from cases.models import StateTransition


class AdminStateTransitionDeleteMutation(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)

    success = graphene.Boolean()

    @staticmethod
    @login_required
    @superuser_required
    def mutate(root, info, id):
        transition = StateTransition.objects.get(pk=id)
        transition.delete()
        return {"success": True}
