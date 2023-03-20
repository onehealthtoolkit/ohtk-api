import graphene
from graphql_jwt.decorators import login_required

from accounts.utils import is_superuser
from ..types import ReportTypeType
from ...models import ReportType


class PublishReportTypeMutation(graphene.Mutation):
    class Arguments:
        report_type_id = graphene.UUID(required=True)

    report_type = graphene.Field(ReportTypeType)

    @staticmethod
    @login_required
    def mutate(root, info, report_type_id):
        user = info.context.user
        if not is_superuser(user):
            raise PermissionError("Only superuser can publish report type")

        report_type = ReportType.objects.get(pk=report_type_id)
        report_type.publish()

        return PublishReportTypeMutation(report_type=report_type)


class UnPublishReportTypeMutation(graphene.Mutation):
    class Arguments:
        report_type_id = graphene.UUID(required=True)

    report_type = graphene.Field(ReportTypeType)

    @staticmethod
    @login_required
    def mutate(root, info, report_type_id):
        user = info.context.user
        if not is_superuser(user):
            raise PermissionError("Only superuser can unpublished report type")

        report_type = ReportType.objects.get(pk=report_type_id)
        report_type.unpublish()

        return UnPublishReportTypeMutation(report_type=report_type)
