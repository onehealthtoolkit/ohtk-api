import graphene
from django.core.exceptions import PermissionDenied
from graphql_jwt.decorators import login_required
from graphene.types.generic import GenericScalar

from reports.models import IncidentReport, FollowUpReport
from reports.followup_permissions import has_followup_permission
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
        followup_id,
    ):
        user = info.context.user
        incident = IncidentReport.objects.get(pk=incident_id)
        if not has_followup_permission(user, incident):
            raise PermissionDenied("village is not assigned to reporter")
        followup = FollowUpReport.objects.create(
            id=followup_id,
            reported_by=user,
            report_type=incident.report_type,
            data=data,
            incident=incident,
        )
        return SubmitFollowupReport(result=followup)
