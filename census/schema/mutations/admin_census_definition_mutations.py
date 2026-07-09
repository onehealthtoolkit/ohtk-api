import graphene
from graphql_jwt.decorators import login_required, superuser_required
from graphene.types.generic import GenericScalar

from census.definition_schema import generate_runtime_schema, validate_definition_schema
from census.rounds import materialize_occurrences, validate_round_definition
from census.census_definition_defaults import (
    default_schema_for_kind,
    default_definition_schema_for_kind,
    ensure_default_census_setup,
    ensure_definition,
    publish_schema_version,
    save_schema_draft,
)
from census.models import (
    CensusDefinition,
    CensusDefinitionVersion,
    CensusRoundDefinition,
)
from census.schema.types import (
    AdminCensusDefinitionSetEnabledPayload,
    AdminCensusDefinitionSetupPayload,
    AdminCensusDefinitionVersionPublishPayload,
    AdminCensusRoundDefinitionSavePayload,
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


class AdminCensusRoundDefinitionSaveMutation(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=False)
        code = graphene.String(required=True)
        name = graphene.String(required=True)
        kind = graphene.String(required=True)
        mode = graphene.String(required=False, default_value="PRODUCTION")
        census_period_start = graphene.String(required=True)
        census_period_end = graphene.String(required=True)
        start_date = graphene.String(required=True)
        soft_finish_date = graphene.String(required=True)
        hard_finish_date = graphene.String(required=True)
        target_authority_id = graphene.Int(required=False)
        enabled = graphene.Boolean(required=False, default_value=True)
        materialize_from_year = graphene.Int(required=False)
        materialize_years = graphene.Int(required=False, default_value=2)

    Output = AdminCensusRoundDefinitionSavePayload

    @staticmethod
    @login_required
    @superuser_required
    def mutate(
        root,
        info,
        code,
        name,
        kind,
        mode="PRODUCTION",
        census_period_start=None,
        census_period_end=None,
        start_date=None,
        soft_finish_date=None,
        hard_finish_date=None,
        id=None,
        target_authority_id=None,
        enabled=True,
        materialize_from_year=None,
        materialize_years=2,
    ):
        fields = []
        if kind not in CensusDefinition.Kind.values:
            fields.append(
                AdminFieldValidationProblem(
                    name="kind", message="unsupported census round kind"
                )
            )
        if mode not in CensusRoundDefinition.Mode.values:
            fields.append(
                AdminFieldValidationProblem(
                    name="mode", message="unsupported census round mode"
                )
            )
        if materialize_years < 1 or materialize_years > 10:
            fields.append(
                AdminFieldValidationProblem(
                    name="materialize_years",
                    message="materialize years must be between 1 and 10",
                )
            )
        if fields:
            return AdminCensusRoundDefinitionSavePayload(
                definition=None, occurrences=[], fields=fields
            )

        definition = (
            CensusRoundDefinition.objects.filter(pk=id).first()
            if id is not None
            else CensusRoundDefinition()
        )
        definition.code = code
        definition.name = name
        definition.kind = kind
        definition.mode = mode
        definition.repeat = CensusRoundDefinition.Repeat.ANNUAL
        definition.census_period_start = census_period_start
        definition.census_period_end = census_period_end
        definition.start_date = start_date
        definition.soft_finish_date = soft_finish_date
        definition.hard_finish_date = hard_finish_date
        definition.target_authority_id = target_authority_id
        definition.enabled = enabled

        fields = [
            AdminFieldValidationProblem(name=name, message=message)
            for name, message in validate_round_definition(definition)
        ]
        fields.extend(_overlap_problems(definition))
        if fields:
            return AdminCensusRoundDefinitionSavePayload(
                definition=definition, occurrences=[], fields=fields
            )

        definition.save()
        occurrences = []
        if enabled and materialize_from_year is not None:
            occurrences = materialize_occurrences(
                definition, materialize_from_year, materialize_years
            )
        return AdminCensusRoundDefinitionSavePayload(
            definition=definition, occurrences=occurrences, fields=[]
        )


def _overlap_problems(definition):
    if definition.mode != CensusRoundDefinition.Mode.PRODUCTION or not definition.enabled:
        return []

    definition_dates = validate_round_definition(definition)
    if definition_dates:
        return []

    from census.rounds import resolve_definition_dates

    target_authority_id = definition.target_authority_id
    current_start = resolve_definition_dates(definition, 2026)["start_date"]
    current_hard = resolve_definition_dates(definition, 2026)["hard_finish_date"]
    queryset = CensusRoundDefinition.objects.filter(
        kind=definition.kind,
        mode=definition.mode,
        enabled=True,
    )
    if definition.pk:
        queryset = queryset.exclude(pk=definition.pk)
    if target_authority_id is None:
        queryset = queryset.filter(target_authority__isnull=True)
    else:
        queryset = queryset.filter(target_authority_id=target_authority_id)

    for existing in queryset:
        existing_dates = resolve_definition_dates(existing, 2026)
        if (
            existing_dates["start_date"] <= current_hard
            and current_start <= existing_dates["hard_finish_date"]
        ):
            return [
                AdminFieldValidationProblem(
                    name="start_date",
                    message="production round submission window overlaps existing definition",
                )
            ]
    return []
