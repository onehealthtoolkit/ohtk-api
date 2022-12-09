import graphene
from graphql_jwt.decorators import login_required
from observations.models import Definition, MonitoringDefinition
from graphql import GraphQLError

from observations.schema.types import (
    AdminDefinitionQueryType,
    AdminMonitoringDefinitionQueryType,
    ObservationDefinitionType,
)
from pagination import DjangoPaginationConnectionField


class Query(graphene.ObjectType):
    observation_definition_get = graphene.Field(
        ObservationDefinitionType, id=graphene.ID(required=True)
    )

    admin_observation_definition_query = DjangoPaginationConnectionField(
        AdminDefinitionQueryType
    )
    admin_observation_monitoring_definition_query = graphene.List(
        AdminMonitoringDefinitionQueryType, definition_id=graphene.ID(required=True)
    )

    @staticmethod
    @login_required
    def resolve_observation_definition_get(root, info, id):
        user = info.context.user
        if not user.is_superuser:
            raise GraphQLError("Permission denied.")
        return Definition.objects.get(pk=id)

    @staticmethod
    @login_required
    def resolve_admin_observation_monitoring_definition_query(
        root, info, definition_id
    ):
        return MonitoringDefinition.objects.filter(definition__id=definition_id)
