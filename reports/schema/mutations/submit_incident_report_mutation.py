import graphene
from django.core.exceptions import PermissionDenied, ValidationError
from graphql_jwt.decorators import login_required
from graphene.types.generic import GenericScalar

from accounts.models import AuthorityUser, Village
from reports.models.report import IncidentReport
from reports.models.report_type import ReportType
from reports.report_location import resolve_incident_report_gps
from reports.schema.types import IncidentReportType
from reports.signals import incident_report_submitted
from threads.models import Thread


class SubmitIncidentReport(graphene.Mutation):
    class Arguments:
        data = GenericScalar(required=True)
        report_type_id = graphene.UUID(required=True)
        incident_date = graphene.Date(required=True)
        report_id = graphene.UUID(required=False)
        # comma separated string: longitude,latitude (existing client/API contract)
        gps_location = graphene.String(required=False)
        incident_in_authority = graphene.Boolean(required=False)
        test_flag = graphene.Boolean(required=False, default_value=False)
        # Dashboard officer create (OP1): village under actor authority tree
        village_id = graphene.Int(required=False)

    result = graphene.Field(IncidentReportType)

    @staticmethod
    @login_required
    def mutate(
        root,
        info,
        data,
        report_type_id,
        incident_date,
        report_id=None,
        gps_location=None,
        incident_in_authority=None,
        test_flag=False,
        village_id=None,
    ):
        # check idempotent
        if report_id and IncidentReport.objects.filter(id=report_id).exists():
            return SubmitIncidentReport(result=IncidentReport.objects.get(id=report_id))

        user = info.context.user
        report_type = ReportType.objects.get(pk=report_type_id)
        location = resolve_incident_report_gps(user, gps_location)
        if incident_in_authority is None:
            incident_in_authority = False

        village = None
        if village_id is not None:
            try:
                village = Village.objects.select_related("authority").get(pk=village_id)
            except Village.DoesNotExist:
                raise ValidationError("village not found")
            if not village.active:
                raise ValidationError("village is not active")
            if not user.is_superuser:
                if not getattr(user, "is_authority_user", False):
                    raise PermissionDenied("not an authority user")
                actor_authority = user.authorityuser.authority
                # Under actor authority hierarchy (admin: down tree; officer: same auth)
                if user.is_authority_role_in([AuthorityUser.Role.OFFICER]):
                    if village.authority_id != actor_authority.id:
                        raise PermissionDenied("village not under officer authority")
                elif user.is_authority_role_in([AuthorityUser.Role.ADMIN]):
                    if not actor_authority.is_in_inherits_down([village.authority_id]):
                        raise PermissionDenied("village not under admin authority")
                elif user.is_authority_role_in([AuthorityUser.Role.REPORTER]):
                    raise PermissionDenied("reporters cannot select village on submit")
            if location is None and village.location is not None:
                location = village.location

        thread = Thread.objects.create()
        report = IncidentReport.objects.create(
            reported_by=user,
            report_type=report_type,
            data=data,
            id=report_id,
            incident_date=incident_date,
            gps_location=location,
            relevant_authority_resolved=bool(
                incident_in_authority or village is not None
            ),
            thread=thread,
            test_flag=test_flag,
        )
        if village is not None:
            report.relevant_authorities.add(village.authority)
        elif incident_in_authority:
            report.relevant_authorities.add(user.authorityuser.authority)
        else:
            report.resolve_relevant_authorities_by_area()

        incident_report_submitted.send(sender=IncidentReport, report=report)

        return SubmitIncidentReport(result=report)
