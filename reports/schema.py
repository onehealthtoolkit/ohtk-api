from typing import List

import graphene
from graphql_jwt.decorators import login_required

from reports.models import ReportType, Category, ZeroReport
from reports.types import (
    ReportTypeType,
    ReportTypeSyncInputType,
    ReportTypeSyncOutputType,
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


class SubmitZeroReportMutation(graphene.Mutation):
    id = graphene.UUID()

    @staticmethod
    @login_required
    def mutate(root, info):
        user = info.context.user
        report = ZeroReport.objects.create(reported_by=user)
        return SubmitZeroReportMutation(id=report.id)


class Mutation(graphene.ObjectType):
    submit_zero_report = SubmitZeroReportMutation.Field()
