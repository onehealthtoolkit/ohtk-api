import json
import graphene
from common.types import AdminFieldValidationProblem
from reports.models.category import Category
from reports.models.report_type import ReportType

from reports.schema.types import (
    AdminReportTypeUpdateProblem,
    AdminReportTypeUpdateResult,
)


class AdminReportTypeUpdateMutation(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)
        name = graphene.String(required=True)
        category_id = graphene.Int(required=True)
        definition = graphene.String(required=True)
        ordering = graphene.Int(required=True)

    result = graphene.Field(AdminReportTypeUpdateResult)

    @staticmethod
    def mutate(root, info, id, name, category_id, definition, ordering):
        reportType = ReportType.objects.get(pk=id)

        if not reportType:
            return AdminReportTypeUpdateMutation(
                result=AdminReportTypeUpdateProblem(
                    fields=[], message="Object not found"
                )
            )

        if reportType.name != name and ReportType.objects.filter(name=name).exists():
            return AdminReportTypeUpdateMutation(
                result=AdminReportTypeUpdateProblem(
                    fields=[
                        AdminFieldValidationProblem(
                            name="name", message="duplicate name"
                        )
                    ]
                )
            )

        reportType.name = name
        reportType.category = Category.objects.get(pk=category_id)
        reportType.definition = json.loads(definition)
        reportType.ordering = ordering
        reportType.save()
        return AdminReportTypeUpdateMutation(result=reportType)
