import graphene
from graphql_jwt.decorators import login_required, superuser_required
from graphene.types.generic import GenericScalar

from accounts.census_definition_defaults import (
    default_schema_for_kind,
    ensure_default_census_setup,
    ensure_definition,
    publish_schema_version,
)
from accounts.models import CensusDefinition
from accounts.schema.types import (
    AdminCensusDefinitionSetupPayload,
    AdminCensusDefinitionVersionPublishPayload,
)
from common.types import AdminFieldValidationProblem


class AdminCensusDefinitionsEnsureDefaultsMutation(graphene.Mutation):
    class Arguments:
        seed_species = graphene.Boolean(required=False, default_value=True)
        reset_schema = graphene.Boolean(required=False, default_value=False)

    Output = AdminCensusDefinitionSetupPayload

    @staticmethod
    @login_required
    @superuser_required
    def mutate(root, info, seed_species=True, reset_schema=False):
        definitions, versions = ensure_default_census_setup(
            seed_species=seed_species, reset_schema=reset_schema
        )
        return AdminCensusDefinitionSetupPayload(
            definitions=definitions, versions=versions, fields=[]
        )


class AdminCensusDefinitionVersionPublishMutation(graphene.Mutation):
    class Arguments:
        kind = graphene.String(required=True)
        schema = GenericScalar(required=False)
        enabled = graphene.Boolean(required=False, default_value=True)

    Output = AdminCensusDefinitionVersionPublishPayload

    @staticmethod
    @login_required
    @superuser_required
    def mutate(root, info, kind, schema=None, enabled=True):
        if kind not in CensusDefinition.Kind.values:
            return AdminCensusDefinitionVersionPublishPayload(
                definition=None,
                version=None,
                fields=[
                    AdminFieldValidationProblem(
                        name="kind", message="unsupported census definition kind"
                    )
                ],
            )

        definition = ensure_definition(
            kind,
            enabled=enabled,
            sort_order=1 if kind == CensusDefinition.Kind.ANIMAL else 2,
        )
        version = publish_schema_version(
            definition, schema if schema is not None else default_schema_for_kind(kind)
        )
        return AdminCensusDefinitionVersionPublishPayload(
            definition=definition, version=version, fields=[]
        )
