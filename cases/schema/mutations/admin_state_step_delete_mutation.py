import graphene
from graphql_jwt.decorators import login_required, superuser_required

from cases.models import StateStep


class AdminStateStepDeleteMutation(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)

    success = graphene.Boolean()

    @staticmethod
    @login_required
    @superuser_required
    def mutate(root, info, id):
        step = StateStep.objects.get(pk=id)
        step.delete()
        return {"success": True}
