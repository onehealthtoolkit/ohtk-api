from typing import List

import graphene
from graphene.types.generic import GenericScalar
from graphql_jwt.decorators import login_required

from reports.models import ReportType, Category, ZeroReport, IncidentReport
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


class SubmitIncidentReport(graphene.Mutation):
    class Arguments:
        data = GenericScalar(required=True)
        report_type_id = graphene.UUID(required=True)
        incident_date = graphene.Date(required=True)
        report_id = graphene.UUID(required=False)

    id = graphene.UUID()
    renderer_data = graphene.String()

    @staticmethod
    @login_required
    def mutate(root, info, data, report_type_id, incident_date, report_id):
        user = info.context.user
        report_type = ReportType.objects.get(pk=report_type_id)
        report = IncidentReport.objects.create(
            reported_by=user,
            report_type=report_type,
            data=data,
            id=report_id,
            incident_date=incident_date,
        )
        return SubmitIncidentReport(
            id=report.id,
            renderer_data=report.renderer_data,
        )


class Mutation(graphene.ObjectType):
    submit_zero_report = SubmitZeroReportMutation.Field()
    submit_incident_report = SubmitIncidentReport.Field()
