import graphene
from common.utils import is_not_empty, check_and_get
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

        problems = []
        report_type, problem = check_and_get(
            "report_type_id", report_type_id, ReportType
        )
        if problem:
            problems.append(problem)

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
