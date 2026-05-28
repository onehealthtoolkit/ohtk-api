import graphene
from django.db import transaction
from graphql import GraphQLError
from graphql_jwt.decorators import login_required
from graphene.types.generic import GenericScalar

from accounts.models import (
    AuthorityUser,
    Village,
    VillageReporterAssignment,
)
from census.animal_census_capability import is_animal_census_capability_enabled
from census.models import (
    AnimalCensusFact,
    AnimalSpecies,
    CensusDefinitionVersion,
    CurrentAnimalCensusFact,
    CurrentHumanCensusFact,
    HumanCensusFact,
    VillageCensusSnapshot,
)
from census.definition_schema import runtime_schema_for_version
from census.schema.types import (
    VillageCensusSnapshotProblem,
    VillageCensusSnapshotResult,
)
from accounts.village_capability import is_village_capability_enabled
from common.types import AdminFieldValidationProblem

ACTIVE_ANIMAL_SPECIES_CHANGED = "ACTIVE_ANIMAL_SPECIES_CHANGED"


class AnimalCensusFactInput(graphene.InputObjectType):
    species_id = graphene.Int(required=True)
    animal_quantity = graphene.Int(required=True)
    household_quantity = graphene.Int(required=True)


def validate_census_capabilities(problems):
    if not is_village_capability_enabled():
        problems.append(
            AdminFieldValidationProblem(
                name="village_enabled", message="village capability is not enabled"
            )
        )
    if not is_animal_census_capability_enabled():
        problems.append(
            AdminFieldValidationProblem(
                name="animal_census_enabled",
                message="animal census capability is not enabled",
            )
        )


def validate_official_assignment(user, village_id, problems):
    if not user.is_authority_role_in([AuthorityUser.Role.REPORTER]):
        problems.append(
            AdminFieldValidationProblem(
                name="reporter", message="only reporter users can submit census"
            )
        )
        return None

    assignment = VillageReporterAssignment.objects.filter(
        reporter=user.authorityuser,
        village_id=village_id,
        census_role=VillageReporterAssignment.CensusRole.OFFICIAL,
    ).first()
    if not assignment:
        problems.append(
            AdminFieldValidationProblem(
                name="village_id",
                message="official reporter assignment is required for village",
            )
        )
    return assignment


def validate_fact_inputs(facts, problems):
    active_species = list(AnimalSpecies.objects.filter(active=True))
    if not active_species:
        problems.append(
            AdminFieldValidationProblem(
                name="facts", message="at least one active species is required"
            )
        )
        return

    active_species_ids = {species.id for species in active_species}
    supplied_species_ids = [fact.species_id for fact in facts]
    supplied_species_id_set = set(supplied_species_ids)

    if len(supplied_species_ids) != len(supplied_species_id_set):
        problems.append(
            AdminFieldValidationProblem(
                name="facts", message="species can be submitted only once"
            )
        )

    missing_species_ids = active_species_ids - supplied_species_id_set
    if missing_species_ids:
        problems.append(
            AdminFieldValidationProblem(
                name="facts", message=ACTIVE_ANIMAL_SPECIES_CHANGED
            )
        )

    invalid_species_ids = supplied_species_id_set - active_species_ids
    if invalid_species_ids:
        problems.append(
            AdminFieldValidationProblem(
                name="facts", message="facts contain unknown or inactive species"
            )
        )

    for fact in facts:
        if fact.animal_quantity < 0 or fact.household_quantity < 0:
            problems.append(
                AdminFieldValidationProblem(
                    name="facts", message="quantities must be zero or greater"
                )
            )
            break


def validate_census_definition_version(definition_version_id, problems):
    try:
        definition_version = CensusDefinitionVersion.objects.select_related(
            "definition"
        ).get(pk=definition_version_id)
    except CensusDefinitionVersion.DoesNotExist:
        problems.append(
            AdminFieldValidationProblem(
                name="definition_version_id",
                message="census definition version does not exist",
            )
        )
        return None

    if not definition_version.definition.enabled:
        problems.append(
            AdminFieldValidationProblem(
                name="definition_version_id", message="DEFINITION_DISABLED"
            )
        )
    if definition_version.status != CensusDefinitionVersion.Status.PUBLISHED:
        problems.append(
            AdminFieldValidationProblem(
                name="definition_version_id",
                message="census definition version must be published",
            )
        )
    return definition_version


def validate_measure_values(submitted_measures, configured_measures, problems):
    measures_by_key = {
        measure.get("key"): measure
        for measure in configured_measures
        if isinstance(measure, dict)
    }
    required_measure_keys = {
        key for key, measure in measures_by_key.items() if measure.get("required")
    }

    missing_measure_keys = required_measure_keys - set(submitted_measures.keys())
    if missing_measure_keys:
        problems.append(
            AdminFieldValidationProblem(
                name="form_data.rows", message="required measures must be submitted"
            )
        )
        return {}

    invalid_measure_keys = set(submitted_measures.keys()) - set(measures_by_key.keys())
    if invalid_measure_keys:
        problems.append(
            AdminFieldValidationProblem(
                name="form_data.rows", message="rows contain unknown measure key"
            )
        )
        return {}

    normalized_measures = {}
    for measure_key, value in submitted_measures.items():
        measure = measures_by_key[measure_key]
        if measure.get("type") == "integer":
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                problems.append(
                    AdminFieldValidationProblem(
                        name="form_data.rows",
                        message="integer measures must be zero or greater",
                    )
                )
                continue
        normalized_measures[measure_key] = value
    return normalized_measures


def validate_common_form_data(form_data, problems):
    if not isinstance(form_data, dict):
        problems.append(
            AdminFieldValidationProblem(
                name="form_data", message="form data must be an object"
            )
        )
        return []

    submitted_rows = form_data.get("rows")
    if not isinstance(submitted_rows, list):
        problems.append(
            AdminFieldValidationProblem(
                name="form_data.rows", message="rows must be a list"
            )
        )
        return []
    return submitted_rows


def validate_animal_form_data(form_data, definition_version, problems):
    submitted_rows = validate_common_form_data(form_data, problems)
    if not submitted_rows:
        return []

    runtime_schema = runtime_schema_for_version(definition_version)
    configured_measures = runtime_schema.get("measures") or []
    configured_rows = runtime_schema.get("rows") or []
    species_by_id = {species.id: species for species in AnimalSpecies.objects.all()}
    rows_by_species_id = {
        row.get("species_id"): row
        for row in configured_rows
        if isinstance(row, dict) and row.get("species_id") is not None
    }
    rows_by_key = {
        row.get("row_key") or row.get("key"): row
        for row in configured_rows
        if isinstance(row, dict) and (row.get("row_key") or row.get("key"))
    }
    required_row_ids = {
        row_identifier(row)
        for row in configured_rows
        if isinstance(row, dict) and row_identifier(row)
    }

    supplied_row_ids = []
    derived_rows = []
    for row in submitted_rows:
        if not isinstance(row, dict):
            problems.append(
                AdminFieldValidationProblem(
                    name="form_data.rows", message="each row must be an object"
                )
            )
            continue

        species_id = row.get("species_id")
        submitted_row_key = row.get("row_key")
        configured_row = (
            rows_by_species_id.get(species_id)
            if species_id is not None
            else rows_by_key.get(submitted_row_key)
        )
        supplied_row_ids.append(row_identifier(configured_row or row))
        if not configured_row:
            problems.append(
                AdminFieldValidationProblem(
                    name="form_data.rows",
                    message="rows contain unknown or inactive species",
                )
            )
            continue

        species = species_by_id.get(configured_row.get("species_id"))
        if not species:
            problems.append(
                AdminFieldValidationProblem(
                    name="form_data.rows",
                    message="rows contain unknown or inactive species",
                )
            )
            continue

        submitted_measures = row.get("measures")
        if not isinstance(submitted_measures, dict):
            problems.append(
                AdminFieldValidationProblem(
                    name="form_data.rows", message="row measures must be an object"
                )
            )
            continue

        submitted_extra_dimensions = row.get("extra_dimensions") or {}
        if not isinstance(submitted_extra_dimensions, dict):
            problems.append(
                AdminFieldValidationProblem(
                    name="form_data.rows", message="extra dimensions must be an object"
                )
            )
            continue
        configured_dimensions = configured_row.get("dimensions") or {}
        if not isinstance(configured_dimensions, dict):
            configured_dimensions = {}

        derived_rows.append(
            {
                "species": species,
                "row_key": configured_row.get("row_key")
                or configured_row.get("key")
                or f"species:{species.code}",
                "extra_dimensions": {
                    **submitted_extra_dimensions,
                    **configured_dimensions,
                },
                "measures": validate_measure_values(
                    submitted_measures, configured_measures, problems
                ),
            }
        )

    supplied_row_id_set = set(supplied_row_ids)
    if len(supplied_row_ids) != len(supplied_row_id_set):
        problems.append(
            AdminFieldValidationProblem(
                name="form_data.rows", message="species can be submitted only once"
            )
        )
    if supplied_row_id_set != required_row_ids:
        problems.append(
            AdminFieldValidationProblem(
                name="form_data.rows", message=ACTIVE_ANIMAL_SPECIES_CHANGED
            )
        )

    return derived_rows


def row_identifier(row):
    if not isinstance(row, dict):
        return None
    if row.get("species_id") is not None:
        return f"species_id:{row.get('species_id')}"
    return row.get("row_key") or row.get("key")


def validate_human_form_data(form_data, definition_version, problems):
    submitted_rows = validate_common_form_data(form_data, problems)
    if not submitted_rows:
        return []

    configured_rows = (definition_version.schema or {}).get("rows") or []
    configured_measures = (definition_version.schema or {}).get("measures") or []
    rows_by_key = {
        row.get("key"): row for row in configured_rows if isinstance(row, dict)
    }

    row_keys = []
    derived_rows = []
    for row in submitted_rows:
        if not isinstance(row, dict):
            problems.append(
                AdminFieldValidationProblem(
                    name="form_data.rows", message="each row must be an object"
                )
            )
            continue

        row_key = row.get("row_key")
        row_keys.append(row_key)
        configured_row = rows_by_key.get(row_key)
        if not configured_row:
            problems.append(
                AdminFieldValidationProblem(
                    name="form_data.rows", message="rows contain unknown row key"
                )
            )
            continue

        submitted_measures = row.get("measures")
        if not isinstance(submitted_measures, dict):
            problems.append(
                AdminFieldValidationProblem(
                    name="form_data.rows", message="row measures must be an object"
                )
            )
            continue

        derived_rows.append(
            {
                "row_key": row_key,
                "dimensions": configured_row.get("dimensions") or {},
                "measures": validate_measure_values(
                    submitted_measures, configured_measures, problems
                ),
            }
        )

    supplied_row_keys = set(row_keys)
    configured_row_keys = set(rows_by_key.keys())
    if len(row_keys) != len(supplied_row_keys):
        problems.append(
            AdminFieldValidationProblem(
                name="form_data.rows", message="rows can be submitted only once"
            )
        )
    if supplied_row_keys != configured_row_keys:
        problems.append(
            AdminFieldValidationProblem(
                name="form_data.rows", message="all configured rows must be submitted"
            )
        )

    return derived_rows


class SubmitVillageCensusSnapshotMutation(graphene.Mutation):
    class Arguments:
        village_id = graphene.Int(required=True)
        census_date = graphene.Date(required=True)
        facts = graphene.List(graphene.NonNull(AnimalCensusFactInput), required=True)

    result = graphene.Field(VillageCensusSnapshotResult)

    @staticmethod
    @login_required
    def mutate(root, info, village_id, census_date, facts):
        problems = []
        validate_census_capabilities(problems)

        try:
            Village.objects.get(pk=village_id)
        except Village.DoesNotExist:
            problems.append(
                AdminFieldValidationProblem(
                    name="village_id", message="village does not exist"
                )
            )

        user = info.context.user
        if not user.is_authority_user:
            raise GraphQLError("Permission denied.")

        validate_official_assignment(user, village_id, problems)
        validate_fact_inputs(facts, problems)

        if problems:
            return SubmitVillageCensusSnapshotMutation(
                result=VillageCensusSnapshotProblem(fields=problems)
            )

        with transaction.atomic():
            snapshot = VillageCensusSnapshot.objects.create(
                village_id=village_id,
                reporter=user.authorityuser,
                census_date=census_date,
            )
            species_by_id = {
                species.id: species
                for species in AnimalSpecies.objects.filter(
                    id__in=[fact.species_id for fact in facts]
                )
            }
            animal_facts = AnimalCensusFact.objects.bulk_create(
                [
                    AnimalCensusFact(
                        snapshot=snapshot,
                        animal_species_id=fact.species_id,
                        row_key=f"species:{species_by_id[fact.species_id].code}",
                        measures={
                            "animal_quantity": fact.animal_quantity,
                            "household_quantity": fact.household_quantity,
                        },
                    )
                    for fact in facts
                ]
            )
            CurrentAnimalCensusFact.objects.filter(
                fact__snapshot__village_id=village_id
            ).delete()
            CurrentAnimalCensusFact.objects.bulk_create(
                [CurrentAnimalCensusFact(fact=fact) for fact in animal_facts]
            )

        return SubmitVillageCensusSnapshotMutation(result=snapshot)


class SubmitVillageCensusSnapshotV2Mutation(graphene.Mutation):
    class Arguments:
        village_id = graphene.Int(required=True)
        definition_version_id = graphene.Int(required=True)
        census_date = graphene.Date(required=True)
        form_data = GenericScalar(required=True)

    result = graphene.Field(VillageCensusSnapshotResult)

    @staticmethod
    @login_required
    def mutate(root, info, village_id, definition_version_id, census_date, form_data):
        problems = []
        validate_census_capabilities(problems)

        try:
            Village.objects.get(pk=village_id)
        except Village.DoesNotExist:
            problems.append(
                AdminFieldValidationProblem(
                    name="village_id", message="village does not exist"
                )
            )

        user = info.context.user
        if not user.is_authority_user:
            raise GraphQLError("Permission denied.")

        validate_official_assignment(user, village_id, problems)
        definition_version = validate_census_definition_version(
            definition_version_id, problems
        )
        derived_rows = []
        if definition_version:
            if definition_version.definition.kind == "ANIMAL":
                derived_rows = validate_animal_form_data(
                    form_data, definition_version, problems
                )
            elif definition_version.definition.kind == "HUMAN":
                derived_rows = validate_human_form_data(
                    form_data, definition_version, problems
                )
            else:
                problems.append(
                    AdminFieldValidationProblem(
                        name="definition_version_id",
                        message="unsupported census definition kind",
                    )
                )

        if problems:
            return SubmitVillageCensusSnapshotV2Mutation(
                result=VillageCensusSnapshotProblem(fields=problems)
            )

        with transaction.atomic():
            snapshot = VillageCensusSnapshot.objects.create(
                village_id=village_id,
                reporter=user.authorityuser,
                definition_version=definition_version,
                census_date=census_date,
                form_data=form_data,
            )
            if definition_version.definition.kind == "ANIMAL":
                animal_facts = AnimalCensusFact.objects.bulk_create(
                    [
                        AnimalCensusFact(
                            snapshot=snapshot,
                            animal_species=row["species"],
                            row_key=row["row_key"],
                            extra_dimensions=row["extra_dimensions"],
                            measures=row["measures"],
                        )
                        for row in derived_rows
                    ]
                )
                CurrentAnimalCensusFact.objects.filter(
                    fact__snapshot__village_id=village_id
                ).delete()
                CurrentAnimalCensusFact.objects.bulk_create(
                    [CurrentAnimalCensusFact(fact=fact) for fact in animal_facts]
                )
            elif definition_version.definition.kind == "HUMAN":
                human_facts = HumanCensusFact.objects.bulk_create(
                    [
                        HumanCensusFact(
                            snapshot=snapshot,
                            row_key=row["row_key"],
                            dimensions=row["dimensions"],
                            measures=row["measures"],
                        )
                        for row in derived_rows
                    ]
                )
                CurrentHumanCensusFact.objects.filter(
                    fact__snapshot__village_id=village_id
                ).delete()
                CurrentHumanCensusFact.objects.bulk_create(
                    [CurrentHumanCensusFact(fact=fact) for fact in human_facts]
                )

        return SubmitVillageCensusSnapshotV2Mutation(result=snapshot)
