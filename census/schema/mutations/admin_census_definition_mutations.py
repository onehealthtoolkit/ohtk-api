import graphene
from graphql_jwt.decorators import login_required, superuser_required
from graphene.types.generic import GenericScalar

from census.definition_schema import generate_runtime_schema, validate_definition_schema
from census.census_definition_defaults import (
    default_schema_for_kind,
    default_definition_schema_for_kind,
    ensure_default_census_setup,
    ensure_definition,
    publish_schema_version,
    save_schema_draft,
)
from census.models import CensusDefinition, CensusDefinitionVersion
from census.schema.types import (
    AdminCensusDefinitionSetEnabledPayload,
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
        definition_schema = GenericScalar(required=False)
        enabled = graphene.Boolean(required=False, default_value=True)

    Output = AdminCensusDefinitionVersionPublishPayload

    @staticmethod
    @login_required
    @superuser_required
    def mutate(root, info, kind, schema=None, definition_schema=None, enabled=True):
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
        if definition_schema is not None:
            validation_errors = validate_definition_schema(definition_schema)
            if validation_errors:
                return AdminCensusDefinitionVersionPublishPayload(
                    definition=definition,
                    version=None,
                    fields=[
                        AdminFieldValidationProblem(name=name, message=message)
                        for name, message in validation_errors
                    ],
                )
            version = publish_schema_version(
                definition,
                generate_runtime_schema(definition_schema),
                definition_schema=definition_schema,
            )
        else:
            version = publish_schema_version(
                definition,
                schema if schema is not None else default_schema_for_kind(kind),
                definition_schema=default_definition_schema_for_kind(kind)
                if schema is None
                else None,
            )
        return AdminCensusDefinitionVersionPublishPayload(
            definition=definition, version=version, fields=[]
        )


class AdminCensusDefinitionVersionSaveDraftMutation(graphene.Mutation):
    class Arguments:
        kind = graphene.String(required=True)
        definition_schema = GenericScalar(required=True)

    Output = AdminCensusDefinitionVersionPublishPayload

    @staticmethod
    @login_required
    @superuser_required
    def mutate(root, info, kind, definition_schema):
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

        sort_order = 1 if kind == CensusDefinition.Kind.ANIMAL else 2
        definition, _created = CensusDefinition.objects.get_or_create(
            kind=kind,
            defaults={"enabled": True, "sort_order": sort_order},
        )
        if definition.sort_order != sort_order:
            definition.sort_order = sort_order
            definition.save(update_fields=["sort_order", "updated_at"])
        validation_errors = validate_definition_schema(definition_schema)
        if validation_errors:
            return AdminCensusDefinitionVersionPublishPayload(
                definition=definition,
                version=None,
                fields=[
                    AdminFieldValidationProblem(name=name, message=message)
                    for name, message in validation_errors
                ],
            )
        version = save_schema_draft(
            definition,
            generate_runtime_schema(definition_schema),
            definition_schema=definition_schema,
        )
        return AdminCensusDefinitionVersionPublishPayload(
            definition=definition, version=version, fields=[]
        )


class AdminCensusDefinitionSetEnabledMutation(graphene.Mutation):
    class Arguments:
        kind = graphene.String(required=True)
        enabled = graphene.Boolean(required=True)

    Output = AdminCensusDefinitionSetEnabledPayload

    @staticmethod
    @login_required
    @superuser_required
    def mutate(root, info, kind, enabled):
        if kind not in CensusDefinition.Kind.values:
            return AdminCensusDefinitionSetEnabledPayload(
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
        version = (
            definition.versions.filter(status=CensusDefinitionVersion.Status.PUBLISHED)
            .order_by("-version")
            .first()
        )
        return AdminCensusDefinitionSetEnabledPayload(
            definition=definition, version=version, fields=[]
        )
