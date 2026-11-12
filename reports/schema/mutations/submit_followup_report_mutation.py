import graphene
from graphql_jwt.decorators import login_required
from graphene.types.generic import GenericScalar

from common.submissions import replay, submission_transaction
from reports.models import IncidentReport, FollowUpReport
from reports.schema.types import FollowupReportType


class SubmitFollowupReport(graphene.Mutation):
    class Arguments:
        data = GenericScalar(required=True)
        incident_id = graphene.UUID(required=True)
        followup_id = graphene.UUID(required=False)

    result = graphene.Field(FollowupReportType)

    @staticmethod
    @login_required
    def mutate(
        root,
        info,
        data,
        incident_id,
        followup_id=None,
    ):
        with submission_transaction(FollowUpReport, followup_id):
            existing = replay(FollowUpReport, followup_id, incident_id=incident_id)
            if existing is not None:
                return SubmitFollowupReport(result=existing)

            user = info.context.user
            incident = IncidentReport.objects.get(pk=incident_id)
            followup = FollowUpReport.objects.create(
                id=followup_id,
                reported_by=user,
                report_type=incident.report_type,
                data=data,
                incident=incident,
            )
            return SubmitFollowupReport(result=followup)
