import graphene
from graphql_jwt.decorators import login_required, superuser_required

from cases.models import NotificationTemplate


class AdminNotificationTemplateDeleteMutation(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)

    success = graphene.Boolean()

    @staticmethod
    @login_required
    @superuser_required
    def mutate(root, info, id):
        template = NotificationTemplate.objects.get(pk=id)
        template.delete()
        return {"success": True}
