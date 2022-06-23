import json
import graphene
from accounts.schema.utils import isNotEmpty
from common.types import AdminFieldValidationProblem
from reports.models.category import Category
from reports.models.report_type import ReportType

from reports.schema.types import (
    AdminReportTypeCreateProblem,
    AdminReportTypeCreateResult,
)


class AdminReportTypeCreateMutation(graphene.Mutation):
    class Arguments:
        name = graphene.String(required=True)
        category_id = graphene.Int(required=True)
        definition = graphene.String(required=True)
        ordering = graphene.Int(required=True)

    result = graphene.Field(AdminReportTypeCreateResult)

    @staticmethod
    def mutate(root, info, name, category_id, definition, ordering):
        problems = []
        if nameProblem := isNotEmpty("name", "Name must not be empty"):
            problems.append(nameProblem)

        if definitionProblem := isNotEmpty(
            "definition", "Definition must not be empty"
        ):
            problems.append(definitionProblem)

        if ReportType.objects.filter(name=name).exists():
            problems.append(
                AdminFieldValidationProblem(name="name", message="duplicate name")
            )

        if len(problems) > 0:
            return AdminReportTypeCreateMutation(
                result=AdminReportTypeCreateProblem(fields=problems)
            )

        reportType = ReportType.objects.create(
            name=name,
            category=Category.objects.get(pk=category_id),
            definition=json.loads(definition),
            ordering=ordering,
        )
        return AdminReportTypeCreateMutation(result=reportType)
