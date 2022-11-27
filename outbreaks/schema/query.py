import graphene
from graphql_jwt.decorators import login_required
from outbreaks.models import Plan

from outbreaks.schema.types import AdminOutbreakPlanQueryType, OutbreakPlanType
from pagination import DjangoPaginationConnectionField


class Query(graphene.ObjectType):
    admin_outbreak_plan_query = DjangoPaginationConnectionField(
        AdminOutbreakPlanQueryType
    )

    outbreak_plan_get = graphene.Field(OutbreakPlanType, id=graphene.Int(required=True))

    @staticmethod
    @login_required
    def resolve_outbreak_plan_get(root, info, id):
        return Plan.objects.get(pk=id)
