import graphene

from observations.schema.types import (
    AdminDefinitionQueryType,
    AdminMonitoringDefinitionQueryType,
)
from pagination import DjangoPaginationConnectionField


class Query(graphene.ObjectType):
    admin_observation_definition_query = DjangoPaginationConnectionField(
        AdminDefinitionQueryType
    )
    admin_observation_monitoring_definition_query = graphene.List(
        AdminMonitoringDefinitionQueryType, definition_id=graphene.ID(required=True)
    )
