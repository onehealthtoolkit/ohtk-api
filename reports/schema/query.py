from typing import List
import graphene
from graphql import GraphQLError
from graphql_jwt.decorators import login_required
from pagination.connection_field import DjangoPaginationConnectionField
from reports.models import ReportType, Category
from reports.models.report import IncidentReport, FollowUpReport
from reports.models.reporter_notification import ReporterNotification

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
)


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
    incident_reports = DjangoPaginationConnectionField(IncidentReportType)
    my_incident_reports = DjangoPaginationConnectionField(IncidentReportType)
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
            .prefetch_related("images", "reported_by", "report_type")
        )
        user = info.context.user
        if user.is_authority_user:
            authority = info.context.user.authorityuser.authority
            child_authorities = authority.all_inherits_down()
            query = query.filter(relevant_authorities__in=child_authorities)

        return query

    @staticmethod
    @login_required
    def resolve_my_incident_reports(root, info, **kwargs):
        user = info.context.user
        return (
            IncidentReport.objects.filter(reported_by=user)
            .order_by("-created_at")
            .prefetch_related("images", "reported_by", "report_type")
        )

    @staticmethod
    @login_required
    def resolve_followups(root, info, incident_id):
        return FollowUpReport.objects.filter(incident__id=incident_id)
