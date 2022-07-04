import graphene

from pagination import DjangoPaginationConnectionField
from .types import CaseType
from ..models import Case


class Query(graphene.ObjectType):
    cases_query = DjangoPaginationConnectionField(CaseType)
    case_get = graphene.Field(CaseType, id=graphene.UUID(required=True))

    @staticmethod
    def resolve_case_get(root, info, id):
        return Case.objects.get(pk=id)
