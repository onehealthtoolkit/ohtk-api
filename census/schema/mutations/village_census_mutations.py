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
    CensusDefinitionVersion,
    CensusRoundDefinition,
    CurrentAnimalCensusFact,
    CurrentHumanCensusFact,
    HumanCensusFact,
    VillageCensusSnapshot,
)
from census.rounds import resolve_submission_occurrence
from census.definition_schema import runtime_schema_for_version
from census.schema.types import (
    VillageCensusSnapshotProblem,
    VillageCensusSnapshotResult,
)
from accounts.village_capability import is_village_capability_enabled
from common.types import AdminFieldValidationProblem

ACTIVE_ANIMAL_SPECIES_CHANGED = "ACTIVE_ANIMAL_SPECIES_CHANGED"
ANIMAL_SUMMARY_KEY = "summary"
VILLAGE_HOUSEHOLD_QUANTITY_KEY = "village_household_quantity"
ANIMAL_HOUSEHOLD_QUANTITY_KEY = "animal_household_quantity"


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
        if isinstance(measure, dict) and measure.get("key")
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


def measures_for_configured_row(configured_row, global_measures):
    """Per-row measures (group vs species) when present; else global list (v1 flat)."""
    row_measures = configured_row.get("measures")
    if isinstance(row_measures, list) and row_measures:
        return row_measures
    return global_measures


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


def validate_animal_summary(form_data, problems):
    if not isinstance(form_data, dict):
        return

    summary = form_data.get(ANIMAL_SUMMARY_KEY)
    if not isinstance(summary, dict):
        problems.append(
            AdminFieldValidationProblem(
                name=f"form_data.{ANIMAL_SUMMARY_KEY}",
                message="animal census household summary is required",
            )
        )
        return

    normalized = {}
    for key in (VILLAGE_HOUSEHOLD_QUANTITY_KEY, ANIMAL_HOUSEHOLD_QUANTITY_KEY):
        value = summary.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            problems.append(
                AdminFieldValidationProblem(
                    name=f"form_data.{ANIMAL_SUMMARY_KEY}.{key}",
                    message="household summary values must be zero or greater",
                )
            )
            continue
        normalized[key] = value

    village_households = normalized.get(VILLAGE_HOUSEHOLD_QUANTITY_KEY)
    animal_households = normalized.get(ANIMAL_HOUSEHOLD_QUANTITY_KEY)
    if (
        village_households is not None
        and animal_households is not None
        and animal_households > village_households
    ):
        problems.append(
            AdminFieldValidationProblem(
                name=f"form_data.{ANIMAL_SUMMARY_KEY}.{ANIMAL_HOUSEHOLD_QUANTITY_KEY}",
                message="animal households cannot exceed village households",
            )
        )


def validate_animal_form_data(form_data, definition_version, problems):
    submitted_rows = validate_common_form_data(form_data, problems)
    validate_animal_summary(form_data, problems)
    if not submitted_rows:
        return []

    runtime_schema = runtime_schema_for_version(definition_version)
    global_measures = runtime_schema.get("measures") or []
    configured_rows = runtime_schema.get("rows") or []
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

        submitted_row_key = row.get("row_key")
        configured_row = rows_by_key.get(submitted_row_key)
        supplied_row_ids.append(row_identifier(configured_row or row))
        if not configured_row:
            problems.append(
                AdminFieldValidationProblem(
                    name="form_data.rows",
                    message="rows contain unknown row key",
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

        row_measures = measures_for_configured_row(configured_row, global_measures)
        derived_rows.append(
            {
                "row_key": configured_row.get("row_key")
                or configured_row.get("key")
                or submitted_row_key,
                "row_label": configured_row.get("label")
                or configured_row.get("row_label")
                or configured_row.get("row_key")
                or configured_row.get("key"),
                "row_kind": configured_row.get("row_kind"),
                "group": configured_row.get("group"),
                "extra_dimensions": {
                    **submitted_extra_dimensions,
                    **configured_dimensions,
                },
                "measures": validate_measure_values(
                    submitted_measures, row_measures, problems
                ),
            }
        )

    supplied_row_id_set = set(supplied_row_ids)
    if len(supplied_row_ids) != len(supplied_row_id_set):
        problems.append(
            AdminFieldValidationProblem(
                name="form_data.rows", message="rows can be submitted only once"
            )
        )
    if supplied_row_id_set != required_row_ids:
        problems.append(
            AdminFieldValidationProblem(
                name="form_data.rows", message=ACTIVE_ANIMAL_SPECIES_CHANGED
            )
        )

    if runtime_schema.get("layout") == "grouped_species":
        validate_grouped_animal_quantities(
            form_data, derived_rows, runtime_schema, problems
        )

    return derived_rows


def validate_grouped_animal_quantities(
    form_data, derived_rows, runtime_schema, problems
):
    """
    Option A rules:
    - group rows: household_quantity only
    - species rows: animal_quantity only
    - if any heads in group > 0 => group HH >= 1
    - if group HH == 0 => all species heads in group == 0
    - each group HH <= animal_household_quantity <= village_household_quantity
    """
    summary = form_data.get(ANIMAL_SUMMARY_KEY) if isinstance(form_data, dict) else None
    animal_households = None
    if isinstance(summary, dict):
        value = summary.get(ANIMAL_HOUSEHOLD_QUANTITY_KEY)
        if isinstance(value, int) and not isinstance(value, bool):
            animal_households = value

    rows_by_key = {row["row_key"]: row for row in derived_rows if row.get("row_key")}
    for group in runtime_schema.get("groups") or []:
        if not isinstance(group, dict):
            continue
        group_key = group.get("key")
        household_row_key = group.get("household_row_key") or f"group:{group_key}"
        species_row_keys = group.get("species_row_keys") or []
        group_row = rows_by_key.get(household_row_key)
        if not group_row:
            continue
        group_hh = (group_row.get("measures") or {}).get("household_quantity")
        if not isinstance(group_hh, int) or isinstance(group_hh, bool):
            continue

        if animal_households is not None and group_hh > animal_households:
            problems.append(
                AdminFieldValidationProblem(
                    name=f"form_data.rows.{household_row_key}",
                    message="group households cannot exceed animal households",
                )
            )

        total_heads = 0
        for species_row_key in species_row_keys:
            species_row = rows_by_key.get(species_row_key)
            if not species_row:
                continue
            heads = (species_row.get("measures") or {}).get("animal_quantity")
            if isinstance(heads, int) and not isinstance(heads, bool):
                total_heads += heads

        if total_heads > 0 and group_hh < 1:
            problems.append(
                AdminFieldValidationProblem(
                    name=f"form_data.rows.{household_row_key}",
                    message="group households must be at least 1 when animal quantity is greater than zero",
                )
            )
        if group_hh == 0 and total_heads > 0:
            problems.append(
                AdminFieldValidationProblem(
                    name=f"form_data.rows.{household_row_key}",
                    message="group animal quantities must be zero when households is zero",
                )
            )


def row_identifier(row):
    if not isinstance(row, dict):
        return None
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


class SubmitVillageCensusSnapshotV2Mutation(graphene.Mutation):
    class Arguments:
        village_id = graphene.Int(required=True)
        definition_version_id = graphene.Int(required=True)
        occurrence_id = graphene.Int(required=False)
        census_date = graphene.Date(required=True)
        form_data = GenericScalar(required=True)

    result = graphene.Field(VillageCensusSnapshotResult)

    @staticmethod
    @login_required
    def mutate(
        root,
        info,
        village_id,
        definition_version_id,
        census_date,
        form_data,
        occurrence_id=None,
    ):
        problems = []
        validate_census_capabilities(problems)

        village = None
        try:
            village = Village.objects.get(pk=village_id)
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
        occurrence, round_resolution = resolve_submission_occurrence(
            occurrence_id, census_date, definition_version, village, problems
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
                round_occurrence=occurrence,
                round_resolution=round_resolution,
                census_date=census_date,
                form_data=form_data,
            )
            if definition_version.definition.kind == "ANIMAL":
                animal_facts = AnimalCensusFact.objects.bulk_create(
                    [
                        AnimalCensusFact(
                            snapshot=snapshot,
                            row_key=row["row_key"],
                            row_label=row["row_label"],
                            extra_dimensions=row["extra_dimensions"],
                            measures=row["measures"],
                        )
                        for row in derived_rows
                    ]
                )
                if occurrence.mode == CensusRoundDefinition.Mode.PRODUCTION:
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
                if occurrence.mode == CensusRoundDefinition.Mode.PRODUCTION:
                    CurrentHumanCensusFact.objects.filter(
                        fact__snapshot__village_id=village_id
                    ).delete()
                    CurrentHumanCensusFact.objects.bulk_create(
                        [CurrentHumanCensusFact(fact=fact) for fact in human_facts]
                    )

        return SubmitVillageCensusSnapshotV2Mutation(result=snapshot)
