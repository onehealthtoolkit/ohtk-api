import graphene
from common.utils import is_not_empty
from cases.models import CaseDefinition
from cases.schema.types import (
    AdminCaseDefinitionCreateProblem,
    AdminCaseDefinitionCreateResult,
)

from reports.models.report_type import ReportType


class AdminCaseDefinitionCreateMutation(graphene.Mutation):
    class Arguments:
        report_type_id = graphene.UUID(required=True)
        description = graphene.String(required=True)
        condition = graphene.String(required=True)
        is_active = graphene.Boolean(required=None, default_value=True)

    result = graphene.Field(AdminCaseDefinitionCreateResult)

    @staticmethod
    def mutate(root, info, report_type_id, description, condition, is_active):
        problems = []
        try:
            report_type = ReportType.objects.get(pk=report_type_id)
        except ReportType.DoesNotExist:
            return AdminCaseDefinitionCreateMutation(
                result=AdminCaseDefinitionCreateProblem(
                    fields=[], message="ReportType object not found"
                )
            )
        if description_problem := is_not_empty(
            "description", description, "Description must not be empty"
        ):
            problems.append(description_problem)

        if len(problems) > 0:
            return AdminCaseDefinitionCreateMutation(
                result=AdminCaseDefinitionCreateProblem(fields=problems)
            )

        case_definition = CaseDefinition.objects.create(
            report_type=report_type,
            description=description,
            condition=condition,
            is_active=is_active,
        )
        return AdminCaseDefinitionCreateMutation(result=case_definition)
