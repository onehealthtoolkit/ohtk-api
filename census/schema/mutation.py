import graphene

from census.schema.mutations import (
    AdminAnimalCensusCapabilityUpdateMutation,
    AdminCensusDefinitionSetEnabledMutation,
    AdminCensusDefinitionsEnsureDefaultsMutation,
    AdminCensusDefinitionVersionSaveDraftMutation,
    AdminCensusDefinitionVersionPublishMutation,
    SubmitVillageCensusSnapshotV2Mutation,
    AdminCensusRoundDefinitionSaveMutation,
)


class Mutation(graphene.ObjectType):
    admin_animal_census_capability_update = (
        AdminAnimalCensusCapabilityUpdateMutation.Field()
    )
    admin_census_definitions_ensure_defaults = (
        AdminCensusDefinitionsEnsureDefaultsMutation.Field()
    )
    admin_census_definition_version_publish = (
        AdminCensusDefinitionVersionPublishMutation.Field()
    )
    admin_census_definition_version_save_draft = (
        AdminCensusDefinitionVersionSaveDraftMutation.Field()
    )
    admin_census_definition_set_enabled = (
        AdminCensusDefinitionSetEnabledMutation.Field()
    )
    admin_census_round_definition_save = AdminCensusRoundDefinitionSaveMutation.Field()
    submit_village_census_snapshot_v2 = SubmitVillageCensusSnapshotV2Mutation.Field()
