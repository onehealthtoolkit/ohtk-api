import json
import graphene
from accounts.schema.utils import isDupliate, isNotEmpty
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
        try:
            reportType = ReportType.objects.get(pk=id)
        except ReportType.DoesNotExist:
            return AdminReportTypeUpdateMutation(
                result=AdminReportTypeUpdateProblem(
                    fields=[], message="Object not found"
                )
            )

        problems = []
        if nameProblem := isNotEmpty("name", "Name must not be empty"):
            problems.append(nameProblem)

        if reportType.name != name:
            if duplicateProblem := isDupliate("name", name, ReportType):
                problems.append(duplicateProblem)

        if len(problems) > 0:
            return AdminReportTypeUpdateMutation(
                result=AdminReportTypeUpdateProblem(fields=problems)
            )

        reportType.name = name
        reportType.category = Category.objects.get(pk=category_id)
        reportType.definition = json.loads(definition)
        reportType.ordering = ordering
        reportType.save()
        return AdminReportTypeUpdateMutation(result=reportType)
