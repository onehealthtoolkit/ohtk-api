import graphene

from outbreaks.schema.types import AdminOutbreakPlanQueryType
from pagination import DjangoPaginationConnectionField


class Query(graphene.ObjectType):
    admin_outbreak_plan_query = DjangoPaginationConnectionField(
        AdminOutbreakPlanQueryType
    )
