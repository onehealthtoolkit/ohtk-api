import graphene
from graphql import GraphQLError
from graphql_jwt.decorators import login_required

from accounts.models import AuthorityUser
from reports.models import IncidentReport
from ..types import CaseType
from reports.schema.types import IncidentReportType
from ...models import Case


class PromoteToCaseMutation(graphene.Mutation):
    class Arguments:
        report_id = graphene.UUID(required=True)

    report = graphene.Field(IncidentReportType)
    case = graphene.Field(CaseType)

    @staticmethod
    @login_required
    def mutate(root, info, report_id):
        report = IncidentReport.objects.get(pk=report_id)

        user = info.context.user
        if not user.is_superuser:
            if user.is_authority_role_in([AuthorityUser.Role.REPORTER]):
                raise GraphQLError("Not authorized to promote report to case")

            if not report.relevant_authorities.filter(pk=user.authority.pk).exists():
                raise GraphQLError("User's authority is not in charge of this report")

        case = Case.promote_from_incident_report(report_id)
        return PromoteToCaseMutation(report=case.report, case=case)
