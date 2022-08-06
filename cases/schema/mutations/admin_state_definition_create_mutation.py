import graphene
from graphql_jwt.decorators import login_required, user_passes_test

from accounts.utils import is_superuser
from common.utils import is_duplicate, is_not_empty, check_and_get
from cases.models import StateDefinition
from cases.schema.types import (
    AdminStateDefinitionCreateProblem,
    AdminStateDefinitionCreateResult,
)

from reports.models.report_type import ReportType


class AdminStateDefinitionCreateMutation(graphene.Mutation):
    class Arguments:
        name = graphene.String(required=True)
        is_default = graphene.Boolean(required=None, default_value=True)

    result = graphene.Field(AdminStateDefinitionCreateResult)

    @staticmethod
    @login_required
    @user_passes_test(is_superuser)
    def mutate(root, info, name, is_default):
        problems = []
        if name_problem := is_not_empty("name", name, "Name must not be empty"):
            problems.append(name_problem)

        if duplicateProblem := is_duplicate("name", name, StateDefinition):
            problems.append(duplicateProblem)

        if len(problems) > 0:
            return AdminStateDefinitionCreateMutation(
                result=AdminStateDefinitionCreateProblem(fields=problems)
            )

        state_definition = StateDefinition.objects.create(
            name=name,
            is_default=is_default,
        )
        return AdminStateDefinitionCreateMutation(result=state_definition)
