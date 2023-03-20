import graphene
from graphql import GraphQLError
from graphql_jwt.decorators import login_required

from accounts.models import AuthorityUser
from accounts.utils import check_is_not_reporter
from ..types import IncidentReportType
from ...models import IncidentReport


class ConvertToTestReportMutation(graphene.Mutation):
    class Arguments:
        report_id = graphene.UUID(required=True)

    report = graphene.Field(IncidentReportType)

    @staticmethod
    @login_required
    def mutate(root, info, report_id):
        report = IncidentReport.objects.get(pk=report_id)
        if report.test_flag:
            return ConvertToTestReportMutation(report=report)

        user = info.context.user
        if not user.is_superuser:
            check_is_not_reporter(user)

            # and report relevant authorities should include user's authority
            if not report.relevant_authorities.filter(pk=user.authority.pk).exists():
                raise GraphQLError("User's authority iis not in charge of this report")

        IncidentReport.convert_to_test_report(report)
        return ConvertToTestReportMutation(report=report)
