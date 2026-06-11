import graphene
from graphql import GraphQLError
from graphql_jwt.decorators import login_required

from accounts.utils import check_is_not_reporter
from integrations.models import RiskAssessment
from integrations.services import (
    clear_current_risk_assessment,
    create_risk_assessment,
)
from ..types import IncidentReportType, RiskAssessmentProjectionType
from ...models import IncidentReport


NO_ASSESSMENT_VALUE = "NO_ASSESSMENT"


class SetReportRiskMutation(graphene.Mutation):
    class Arguments:
        report_id = graphene.UUID(required=True)
        level = graphene.String(required=False)

    report = graphene.Field(IncidentReportType)
    risk_assessment = graphene.Field(RiskAssessmentProjectionType)

    @staticmethod
    @login_required
    def mutate(root, info, report_id, level=None):
        report = IncidentReport.objects.get(pk=report_id)
        user = info.context.user
        _assert_can_set_report_risk(user, report)

        normalized_level = level.upper() if level else None
        if normalized_level in (None, "", NO_ASSESSMENT_VALUE):
            clear_current_risk_assessment(report=report)
            return SetReportRiskMutation(report=report, risk_assessment=None)

        if normalized_level not in RiskAssessment.Level.values:
            raise GraphQLError("Invalid risk level")

        result = create_risk_assessment(
            report=report,
            level=normalized_level,
            source=RiskAssessment.Source.HUMAN,
            created_by=user,
        )
        return SetReportRiskMutation(
            report=report,
            risk_assessment=result.assessment,
        )


def _assert_can_set_report_risk(user, report):
    if user.is_superuser:
        return

    check_is_not_reporter(user)

    if not user.is_authority_user:
        raise GraphQLError("User is not authority user")

    authority = user.authorityuser.authority
    if not report.relevant_authorities.filter(
        pk__in=[item.pk for item in authority.all_inherits_down()]
    ).exists():
        raise GraphQLError("User's authority is not in charge of this report")
