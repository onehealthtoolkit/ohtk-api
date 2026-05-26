import graphene

from census.schema.mutations import (
    AdminAnimalCensusCapabilityUpdateMutation,
    AdminAnimalSpeciesCreateMutation,
    AdminAnimalSpeciesUpdateMutation,
    AdminCensusDefinitionsEnsureDefaultsMutation,
    AdminCensusDefinitionVersionPublishMutation,
    SubmitVillageCensusSnapshotMutation,
    SubmitVillageCensusSnapshotV2Mutation,
)


class Mutation(graphene.ObjectType):
    admin_animal_census_capability_update = (
        AdminAnimalCensusCapabilityUpdateMutation.Field()
    )
    admin_animal_species_create = AdminAnimalSpeciesCreateMutation.Field()
    admin_animal_species_update = AdminAnimalSpeciesUpdateMutation.Field()
    admin_census_definitions_ensure_defaults = (
        AdminCensusDefinitionsEnsureDefaultsMutation.Field()
    )
    admin_census_definition_version_publish = (
        AdminCensusDefinitionVersionPublishMutation.Field()
    )
    submit_village_census_snapshot = SubmitVillageCensusSnapshotMutation.Field()
    submit_village_census_snapshot_v2 = SubmitVillageCensusSnapshotV2Mutation.Field()
