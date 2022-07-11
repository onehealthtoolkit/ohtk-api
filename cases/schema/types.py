import graphene
from graphene_django import DjangoObjectType

from accounts.schema.types import AuthorityType
from cases.models import Case, CaseDefinition, StateDefinition
from common.types import AdminValidationProblem
from reports.schema.types import IncidentReportType


class StateDefinitionType(DjangoObjectType):
    class Meta:
        model = StateDefinition
        fields = ["id", "name"]


class CaseType(DjangoObjectType):
    state_definition = graphene.Field(StateDefinitionType)
    report = graphene.Field(IncidentReportType)
    authorities = graphene.List(AuthorityType)

    class Meta:
        model = Case
        fields = [
            "id",
            "report",
            "state_definition",
            "description",
            "authorities",
        ]
        filter_fields = {
            "report__created_at": ["lte", "gte"],
            "report__relevant_authorities__id": ["in"],
        }

    def resolve_authorities(root, info):
        return root.authorities.all()


# CaseDefinitionType
class CaseDefinitionType(DjangoObjectType):
    class Meta:
        model = CaseDefinition
        fields = [
            "id",
            "report_type",
            "description",
            "condition",
            "is_active",
        ]


class AdminCaseDefinitionQueryType(DjangoObjectType):
    class Meta:
        model = CaseDefinition
        fields = ("id", "report_type", "description", "condition")
        filter_fields = {
            "description": ["istartswith", "exact"],
        }


class AdminCaseDefinitionCreateSuccess(DjangoObjectType):
    class Meta:
        model = CaseDefinition


class AdminCaseDefinitionCreateProblem(AdminValidationProblem):
    pass


class AdminCaseDefinitionCreateResult(graphene.Union):
    class Meta:
        types = (
            AdminCaseDefinitionCreateSuccess,
            AdminCaseDefinitionCreateProblem,
        )


class AdminCaseDefinitionUpdateSuccess(graphene.ObjectType):
    case_definition = graphene.Field(CaseDefinitionType)


class AdminCaseDefinitionUpdateProblem(AdminValidationProblem):
    pass


class AdminCaseDefinitionUpdateResult(graphene.Union):
    class Meta:
        types = (
            AdminCaseDefinitionUpdateSuccess,
            AdminCaseDefinitionUpdateProblem,
        )
