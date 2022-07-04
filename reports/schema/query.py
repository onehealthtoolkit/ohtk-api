from typing import List
from unicodedata import category
import graphene
from graphql import GraphQLError
from graphql_jwt.decorators import login_required
from pagination.connection_field import DjangoPaginationConnectionField
from reports.models import ReportType, Category
from reports.models.report import IncidentReport

from .types import (
    AdminCategoryQueryType,
    AdminReportTypeQueryType,
    CategoryType,
    IncidentReportType,
    ReportTypeSyncInputType,
    ReportTypeSyncOutputType,
    ReportTypeType,
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
    incident_report = graphene.Field(IncidentReportType, id=graphene.ID(required=True))

    admin_category_query = DjangoPaginationConnectionField(AdminCategoryQueryType)
    admin_report_type_query = DjangoPaginationConnectionField(AdminReportTypeQueryType)

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
    def resolve_category(root, info, id):
        user = info.context.user
        if not user.is_superuser:
            raise GraphQLError("Permission denied.")
        return Category.objects.get(id=id)

    @staticmethod
    def resolve_report_type(root, info, id):
        user = info.context.user
        if not user.is_superuser:
            raise GraphQLError("Permission denied.")
        return ReportType.objects.get(id=id)

    @staticmethod
    def resolve_incident_report(root, info, id):
        user = info.context.user
        if not user.is_superuser:
            raise GraphQLError("Permission denied.")
        return IncidentReport.objects.get(id=id)

    @staticmethod
    def resolve_incident_reports(root, info, **kwargs):
        query = (
            IncidentReport.objects.all()
            .order_by("-created_at")
            .prefetch_related("images", "reported_by", "report_type")
        )
        user = info.context.user
        if user.is_authority_user():
            authority = info.context.user.authorityuser.authority
            child_authorities = authority.all_inherits_down()
            query = query.filter(relevant_authorities__in=child_authorities)

        return query
