import graphene
from graphql_jwt.decorators import login_required
from graphene.types.generic import GenericScalar

from cases.tasks import (
    evaluate_case_definition,
    evaluate_notification_template_after_receive_report,
)
from reports.models.report import IncidentReport
from django.contrib.gis.geos import Point
from reports.models.report_type import ReportType
from reports.schema.types import IncidentReportType
from reports.signals import incident_report_submitted
from reports.tasks import evaluate_reporter_notification
from threads.models import Thread


class SubmitIncidentReport(graphene.Mutation):
    class Arguments:
        data = GenericScalar(required=True)
        report_type_id = graphene.UUID(required=True)
        incident_date = graphene.Date(required=True)
        report_id = graphene.UUID(required=False)
        gps_location = graphene.String(
            required=False
        )  # comma separated string eg. 13.234343,100.23434343 (latitude, longitude)
        incident_in_authority = graphene.Boolean(required=False)

    result = graphene.Field(IncidentReportType)

    @staticmethod
    @login_required
    def mutate(
        root,
        info,
        data,
        report_type_id,
        incident_date,
        report_id,
        gps_location,
        incident_in_authority,
    ):
        user = info.context.user
        report_type = ReportType.objects.get(pk=report_type_id)
        location = None
        if gps_location:
            [longitude, latitude] = gps_location.split(",")
            location = Point(float(longitude), float(latitude))
        if incident_in_authority is None:
            incident_in_authority = False

        thread = Thread.objects.create()
        report = IncidentReport.objects.create(
            reported_by=user,
            report_type=report_type,
            data=data,
            id=report_id,
            incident_date=incident_date,
            gps_location=location,
            relevant_authority_resolved=incident_in_authority,
            thread=thread,
        )
        if incident_in_authority:
            report.relevant_authorities.add(user.authorityuser.authority)
        else:
            report.resolve_relevant_authorities_by_area()

        incident_report_submitted.send(sender=IncidentReport, report=report)

        return SubmitIncidentReport(result=report)
