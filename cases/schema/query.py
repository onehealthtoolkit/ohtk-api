import graphene

from pagination import DjangoPaginationConnectionField
from .types import AdminCaseDefinitionQueryType, CaseDefinitionType, CaseType
from ..models import Case, CaseDefinition


class Query(graphene.ObjectType):
    cases_query = DjangoPaginationConnectionField(CaseType)
    case_get = graphene.Field(CaseType, id=graphene.UUID(required=True))
    case_definition_get = graphene.Field(
        CaseDefinitionType, id=graphene.ID(required=True)
    )
    admin_case_definition_query = DjangoPaginationConnectionField(
        AdminCaseDefinitionQueryType
    )

    @staticmethod
    def resolve_case_get(root, info, id):
        return Case.objects.get(pk=id)

    @staticmethod
    def resolve_case_definition_get(root, info, id):
        return CaseDefinition.objects.get(pk=id)
