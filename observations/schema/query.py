import graphene

from observations.schema.types import AdminObservationDefinitionQueryType
from pagination import DjangoPaginationConnectionField


class Query(graphene.ObjectType):
    admin_observation_definition_query = DjangoPaginationConnectionField(
        AdminObservationDefinitionQueryType
    )
