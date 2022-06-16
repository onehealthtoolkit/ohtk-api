import graphene
from graphql_jwt.decorators import login_required

from reports.models.report import ZeroReport


class SubmitZeroReportMutation(graphene.Mutation):
    id = graphene.UUID()

    @staticmethod
    @login_required
    def mutate(root, info):
        user = info.context.user
        report = ZeroReport.objects.create(reported_by=user)
        return SubmitZeroReportMutation(id=report.id)
