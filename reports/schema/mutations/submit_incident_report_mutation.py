import graphene
from graphql_jwt.decorators import login_required
from graphene.types.generic import GenericScalar
from reports.models.report import IncidentReport
from django.contrib.gis.geos import Point
from reports.models.report_type import ReportType


class SubmitIncidentReport(graphene.Mutation):
    class Arguments:
        data = GenericScalar(required=True)
        report_type_id = graphene.UUID(required=True)
        incident_date = graphene.Date(required=True)
        report_id = graphene.UUID(required=False)
        gps_location = graphene.String(
            required=False
        )  # comma separated string eg. 13.234343,100.23434343

    id = graphene.UUID()
    renderer_data = graphene.String()

    @staticmethod
    @login_required
    def mutate(
        root, info, data, report_type_id, incident_date, report_id, gps_location
    ):
        user = info.context.user
        report_type = ReportType.objects.get(pk=report_type_id)
        location = None
        if gps_location:
            [latitude, longitude] = gps_location.split(",")
            location = Point(float(latitude), float(longitude))
        report = IncidentReport.objects.create(
            reported_by=user,
            report_type=report_type,
            data=data,
            id=report_id,
            incident_date=incident_date,
            gps_location=location,
        )
        return SubmitIncidentReport(
            id=report.id,
            renderer_data=report.renderer_data,
        )
