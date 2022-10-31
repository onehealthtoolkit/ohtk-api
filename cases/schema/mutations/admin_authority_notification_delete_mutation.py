import graphene
from graphql_jwt.decorators import login_required, superuser_required

from cases.models import AuthorityNotification


class AdminAuthorityNotificationDeleteMutation(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)

    success = graphene.Boolean()

    @staticmethod
    @login_required
    @superuser_required
    def mutate(root, info, id):
        definition = AuthorityNotification.objects.get(pk=id)
        definition.delete(hard=True)
        return {"success": True}
