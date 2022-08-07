import graphene
from graphql_jwt.decorators import login_required, superuser_required

from cases.models import StateDefinition


class AdminStateDefinitionDeleteMutation(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)

    success = graphene.Boolean()

    @staticmethod
    @login_required
    @superuser_required
    def mutate(root, info, id):
        definition = StateDefinition.objects.get(pk=id)
        definition.delete()
        return {"success": True}
