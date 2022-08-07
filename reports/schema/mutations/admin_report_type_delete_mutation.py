import graphene
from graphql_jwt.decorators import login_required, superuser_required

from reports.models import ReportType


class AdminReportTypeDeleteMutation(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)

    success = graphene.Boolean()

    @staticmethod
    @login_required
    @superuser_required
    def mutate(root, info, id):
        report_type = ReportType.objects.get(pk=id)
        report_type.delete()
        return {"success": True}
