import graphene
from graphql_jwt.decorators import login_required

from outbreaks.models import Place
from outbreaks.schema.types import AdminOutbreakPlanQueryType, OutbreakPlaceType
from pagination import DjangoPaginationConnectionField


class Query(graphene.ObjectType):
    admin_outbreak_plan_query = DjangoPaginationConnectionField(
        AdminOutbreakPlanQueryType
    )
    outbreak_places = graphene.List(
        OutbreakPlaceType, case_id=graphene.UUID(required=True)
    )

    @staticmethod
    @login_required
    def resolve_outbreak_places(root, info, case_id):
        return Place.objects.filter(case_id=case_id)
