import graphene
from graphql import GraphQLError
from graphql_jwt.decorators import login_required

from accounts.models import AuthorityUser
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
            if user.is_authority_role_in([AuthorityUser.Role.REPORTER]):
                raise GraphQLError("Not authorized to convert report to test report")

            # and report relevant authorities should include user's authority
            if not report.relevant_authorities.filter(pk=user.authority.pk).exists():
                raise GraphQLError("User's authority iis not in charge of this report")

        IncidentReport.convert_to_test_report(report)
        return ConvertToTestReportMutation(report=report)
