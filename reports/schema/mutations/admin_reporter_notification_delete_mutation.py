import graphene
from graphql_jwt.decorators import login_required, superuser_required

from reports.models import ReporterNotification


class AdminReporterNotificationDeleteMutation(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)

    success = graphene.Boolean()

    @staticmethod
    @login_required
    @superuser_required
    def mutate(root, info, id):
        notification = ReporterNotification.objects.get(pk=id)
        notification.delete()
        return {"success": True}
