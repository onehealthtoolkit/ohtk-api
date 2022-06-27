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
            report_type = ReportType.objects.get(pk=id)
        except ReportType.DoesNotExist:
            return AdminReportTypeUpdateMutation(
                result=AdminReportTypeUpdateProblem(
                    fields=[], message="Object not found"
                )
            )

        problems = []
        if name_problem := isNotEmpty("name", "Name must not be empty"):
            problems.append(name_problem)

        if report_type.name != name:
            if dumplicate_problem := isDupliate("name", name, ReportType):
                problems.append(dumplicate_problem)

        if len(problems) > 0:
            return AdminReportTypeUpdateMutation(
                result=AdminReportTypeUpdateProblem(fields=problems)
            )

        report_type.name = name
        report_type.category = Category.objects.get(pk=category_id)
        report_type.definition = json.loads(definition)
        report_type.ordering = ordering
        report_type.save()
        return AdminReportTypeUpdateMutation(result=report_type)
