import graphene

from observations.schema.mutations.admin_observation_definition_mutations import (
    AdminObservationDefinitionCreateMutation,
    AdminObservationDefinitionUpdateMutation,
    AdminObservationDefinitionDeleteMutation,
)
from observations.schema.mutations.admin_observation_monitoring_definition_mutations import (
    AdminObservationMonitoringDefinitionCreateMutation,
    AdminObservationMonitoringDefinitionDeleteMutation,
    AdminObservationMonitoringDefinitionUpdateMutation,
)


class Mutation(graphene.ObjectType):
    admin_observation_definition_create = (
        AdminObservationDefinitionCreateMutation.Field()
    )
    admin_observation_definition_update = (
        AdminObservationDefinitionUpdateMutation.Field()
    )
    admin_observation_definition_delete = (
        AdminObservationDefinitionDeleteMutation.Field()
    )

    admin_observation_monitoring_definition_create = (
        AdminObservationMonitoringDefinitionCreateMutation.Field()
    )
    admin_observation_monitoring_definition_update = (
        AdminObservationMonitoringDefinitionUpdateMutation.Field()
    )
    admin_observation_monitoring_definition_delete = (
        AdminObservationMonitoringDefinitionDeleteMutation.Field()
    )
