import graphene

from observations.schema.mutations.admin_observation_definition_mutations import (
    AdminObservationDefinitionCreateMutation,
    AdminObservationDefinitionUpdateMutation,
    AdminObservationDefinitionDeleteMutation,
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
