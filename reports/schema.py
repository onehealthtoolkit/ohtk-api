from typing import List

import graphene
from graphene.types.generic import GenericScalar
from graphene_file_upload.scalars import Upload
from graphql_jwt.decorators import login_required
from accounts.schema.types import AdminFieldValidationProblem
from pagination.connection_field import DjangoPaginationConnectionField

from reports.models import (
    ReportType,
    Category,
    ZeroReport,
    IncidentReport,
    FollowUpReport,
    Image,
)
from reports.types import (
    AdminCategoryCreateProblem,
    AdminCategoryCreateResult,
    AdminCategoryQueryType,
    AdminCategoryUpdateProblem,
    AdminCategoryUpdateResult,
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

    adminCategoryQuery = DjangoPaginationConnectionField(AdminCategoryQueryType)


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


class SubmitImage(graphene.Mutation):
    class Arguments:
        report_id = graphene.UUID(required=True)
        image = Upload(
            required=True,
        )
        is_cover = graphene.Boolean(required=False)
        image_id = graphene.UUID(required=False)

    id = graphene.UUID()
    url = graphene.String()

    @staticmethod
    @login_required
    def mutate(root, info, report_id, image, is_cover, image_id):
        try:
            report = IncidentReport.objects.get(pk=report_id)
        except IncidentReport.DoesNotExist:
            report = FollowUpReport.objects.get(pk=report_id)

        image = Image.objects.create(
            report=report,
            file=image,
            id=image_id,
        )

        if is_cover:
            report.cover_image_id = image.id
            report.save(update_fields=("cover_image_id"))
        return SubmitImage(id=image.id, url=image.file.url)


class AdminCategoryCreateMutation(graphene.Mutation):
    class Arguments:
        name = graphene.String(required=True)
        ordering = graphene.Int(required=True)

    result = graphene.Field(AdminCategoryCreateResult)

    @staticmethod
    def mutate(
        root,
        info,
        name,
        ordering,
    ):
        if Category.objects.filter(name=name).exists():
            return AdminCategoryCreateMutation(
                result=AdminCategoryCreateProblem(
                    fields=[
                        AdminFieldValidationProblem(
                            name="name", message="duplicate name"
                        )
                    ]
                )
            )

        if not name:
            return AdminCategoryCreateMutation(
                result=AdminCategoryCreateProblem(
                    fields=[
                        AdminFieldValidationProblem(
                            name="name", message="name must not be empty"
                        )
                    ]
                )
            )

        category = Category.objects.create(
            name=name,
            ordering=ordering,
        )
        return AdminCategoryCreateMutation(result=category)


class AdminCategoryUpdateMutation(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)
        name = graphene.String(required=True)
        ordering = graphene.Int(required=True)

    result = graphene.Field(AdminCategoryUpdateResult)

    @staticmethod
    def mutate(root, info, id, name, ordering):
        category = Category.objects.get(pk=id)

        if not category:
            return AdminCategoryUpdateMutation(
                result=AdminCategoryUpdateProblem(fields=[], message="Object not found")
            )

        if category.name != name and Category.objects.filter(name=name).exists():
            return AdminCategoryUpdateMutation(
                result=AdminCategoryUpdateProblem(
                    fields=[
                        AdminFieldValidationProblem(
                            name="name", message="duplicate name"
                        )
                    ]
                )
            )

        category.name = name
        category.ordering = ordering
        category.save()
        return AdminCategoryUpdateMutation(result=category)


class Mutation(graphene.ObjectType):
    submit_zero_report = SubmitZeroReportMutation.Field()
    submit_incident_report = SubmitIncidentReport.Field()
    submit_image = SubmitImage.Field()
    admin_category_create = AdminCategoryCreateMutation.Field()
    admin_category_update = AdminCategoryUpdateMutation.Field()
