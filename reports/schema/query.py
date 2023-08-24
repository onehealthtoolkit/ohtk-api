from typing import List
import graphene
from graphql import GraphQLError
from graphql_jwt.decorators import login_required
from accounts.models import Authority
from pagination.connection_field import DjangoPaginationConnectionField
from reports.models import ReportType, Category
from reports.models.report import IncidentReport, FollowUpReport
from reports.models.reporter_notification import ReporterNotification
from reports.summary.reporter_report_detail_by_day import report_by_day

from .types import (
    AdminCategoryQueryType,
    AdminReportTypeQueryType,
    AdminReporterNotificationQueryType,
    CategoryType,
    IncidentReportType,
    ReportTypeSyncInputType,
    ReportTypeSyncOutputType,
    ReportTypeType,
    ReporterNotificationType,
    FollowupReportType,
    ReporterReportByDate,
    ReporterNoReport,
)
from ..summary.reporter_no_report import no_report


class Query(graphene.ObjectType):
    my_report_types = graphene.List(ReportTypeType)
    sync_report_types = graphene.Field(
        ReportTypeSyncOutputType,
        args={
            "data": graphene.List(
                graphene.NonNull(ReportTypeSyncInputType), required=True
            )
        },
    )
    category = graphene.Field(CategoryType, id=graphene.ID(required=True))
    report_type = graphene.Field(ReportTypeType, id=graphene.ID(required=True))
    report_type_by_name = graphene.Field(
        ReportTypeType, name=graphene.String(required=True)
    )
    incident_reports = DjangoPaginationConnectionField(IncidentReportType)
    my_incident_reports = DjangoPaginationConnectionField(IncidentReportType)
    boundary_connected_incident_reports = DjangoPaginationConnectionField(
        IncidentReportType
    )
    incident_report = graphene.Field(IncidentReportType, id=graphene.ID(required=True))
    followup_report = graphene.Field(FollowupReportType, id=graphene.ID(required=True))
    reporter_notification = graphene.Field(
        ReporterNotificationType, id=graphene.ID(required=True)
    )

    admin_category_query = DjangoPaginationConnectionField(AdminCategoryQueryType)
    admin_report_type_query = DjangoPaginationConnectionField(AdminReportTypeQueryType)
    admin_reporter_notification_query = DjangoPaginationConnectionField(
        AdminReporterNotificationQueryType
    )

    followups = graphene.List(
        FollowupReportType, incident_id=graphene.ID(required=True)
    )

    summary_reporter_report_by_day = graphene.List(
        ReporterReportByDate,
        authority_id=graphene.Int(required=True),
        from_date=graphene.Date(required=True),
        to_date=graphene.Date(required=True),
    )

    summary_reporter_no_report = graphene.List(
        ReporterNoReport,
        authority_id=graphene.Int(required=True),
        from_date=graphene.Date(required=True),
        to_date=graphene.Date(required=True),
    )

    @staticmethod
    @login_required
    def resolve_my_report_types(root, info):
        user = info.context.user
        authority = user.authorityuser.authority
        return ReportType.filter_by_authority(authority)

    @staticmethod
    @login_required
    def resolve_sync_report_types(root, info, data: List[ReportTypeSyncInputType]):
        user = info.context.user
        authority = user.authorityuser.authority
        sync_items = list(map(lambda item: item.to_report_type_data(), data))
        result = ReportType.check_updated_report_types_by_authority(
            authority, sync_items
        )
        return ReportTypeSyncOutputType(
            updated_list=result["updated_list"],
            removed_list=result["removed_list"],
            category_list=Category.objects.all(),
        )

    @staticmethod
    @login_required
    def resolve_category(root, info, id):
        user = info.context.user
        return Category.objects.get(id=id)

    @staticmethod
    @login_required
    def resolve_report_type(root, info, id):
        user = info.context.user
        return ReportType.objects.get(id=id)

    @staticmethod
    @login_required
    def resolve_report_type_by_name(root, info, name):
        user = info.context.user
        return ReportType.objects.get(name=name)

    @staticmethod
    @login_required
    def resolve_incident_report(root, info, id):
        user = info.context.user
        return IncidentReport.objects.get(id=id)

    @staticmethod
    @login_required
    def resolve_followup_report(root, info, id):
        return FollowUpReport.objects.get(id=id)

    @staticmethod
    @login_required
    def resolve_reporter_notification(root, info, id):
        user = info.context.user
        if not user.is_superuser:
            raise GraphQLError("Permission denied.")
        return ReporterNotification.objects.get(id=id)

    @staticmethod
    @login_required
    def resolve_incident_reports(root, info, **kwargs):
        query = (
            IncidentReport.objects.all()
            .order_by("-created_at")
            .prefetch_related("images", "upload_files", "reported_by", "report_type")
        )
        user = info.context.user
        if user.is_authority_user:
            authority = info.context.user.authorityuser.authority
            child_authorities = authority.all_inherits_down()
            query = query.filter(relevant_authorities__in=child_authorities).distinct()

        return query

    @staticmethod
    @login_required
    def resolve_my_incident_reports(root, info, **kwargs):
        user = info.context.user
        authority = info.context.user.authorityuser.authority
        return (
            IncidentReport.objects.filter(
                reported_by=user, relevant_authorities__in=[authority]
            )
            .order_by("-created_at")
            .prefetch_related("images", "upload_files", "reported_by", "report_type")
        )

    @staticmethod
    @login_required
    def resolve_followups(root, info, incident_id):
        return FollowUpReport.objects.filter(incident__id=incident_id)

    @staticmethod
    @login_required
    def resolve_summary_reporter_report_by_day(
        root, info, authority_id, from_date, to_date
    ):
        user = info.context.user
        user_authority = user.authorityuser.authority
        filter_authority = Authority.objects.get(id=authority_id)

        if filter_authority not in user_authority.all_inherits_down():
            raise GraphQLError("Permission denied.")

        return report_by_day(filter_authority.id, from_date, to_date)

    @staticmethod
    @login_required
    def resolve_summary_reporter_no_report(
        root, info, authority_id, from_date, to_date
    ):
        user = info.context.user
        user_authority = user.authorityuser.authority
        filter_authority = Authority.objects.get(id=authority_id)

        if filter_authority not in user_authority.all_inherits_down():
            raise GraphQLError("Permission denied.")

        return no_report(filter_authority.id, from_date, to_date)

    @staticmethod
    @login_required
    def resolve_boundary_connected_incident_reports(root, info, **kwargs):
        query = (
            IncidentReport.objects.all()
            .order_by("-created_at")
            .prefetch_related("images", "upload_files", "reported_by", "report_type")
        )
        user = info.context.user
        if user.is_authority_user:
            authority = user.authorityuser.authority
            all_authorities = []
            child_authorities = authority.all_inherits_down()

            for child_authority in child_authorities:
                boundary_connect_authorities = child_authority.boundary_connects.all()

                print(boundary_connect_authorities)
                all_authorities.extend(boundary_connect_authorities)
                print(all_authorities)

            query = query.filter(relevant_authorities__in=all_authorities).distinct()

        return query
