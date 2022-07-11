import graphene
from common.utils import is_not_empty
from cases.models import CaseDefinition
from cases.schema.types import (
    AdminCaseDefinitionUpdateProblem,
    AdminCaseDefinitionUpdateResult,
    AdminCaseDefinitionUpdateSuccess,
)
from reports.models.report_type import ReportType


class AdminCaseDefinitionUpdateMutation(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)
        report_type_id = graphene.UUID(required=True)
        description = graphene.String(required=True)
        condition = graphene.String(required=True)
        is_active = graphene.Boolean(required=None, default_value=True)

    result = graphene.Field(AdminCaseDefinitionUpdateResult)

    @staticmethod
    def mutate(root, info, id, report_type_id, description, condition, is_active):
        try:
            case_definition = CaseDefinition.objects.get(pk=id)
        except CaseDefinition.DoesNotExist:
            return AdminCaseDefinitionUpdateMutation(
                result=AdminCaseDefinitionUpdateProblem(
                    fields=[], message="Object not found"
                )
            )

        try:
            report_type = ReportType.objects.get(pk=report_type_id)
        except ReportType.DoesNotExist:
            return AdminCaseDefinitionUpdateMutation(
                result=AdminCaseDefinitionUpdateProblem(
                    fields=[], message="ReportType object not found"
                )
            )

        problems = []

        if description_problem := is_not_empty(
            "description", description, "Description must not be empty"
        ):
            problems.append(description_problem)

        if len(problems) > 0:
            return AdminCaseDefinitionUpdateMutation(
                result=AdminCaseDefinitionUpdateProblem(fields=problems)
            )

        case_definition.report_type = report_type
        case_definition.description = description
        case_definition.condition = condition
        case_definition.is_active = is_active
        case_definition.save()
        return AdminCaseDefinitionUpdateMutation(
            result=AdminCaseDefinitionUpdateSuccess(case_definition=case_definition)
        )
