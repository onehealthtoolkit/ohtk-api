from itertools import product


SUPPORTED_MEASURE_TYPES = {"integer"}
GROUP_ROW_KIND = "group"
SPECIES_ROW_KIND = "species"


def is_grouped_animal_schema(definition_schema):
    """Option A: shared group HH + per-species heads."""
    if not isinstance(definition_schema, dict):
        return False
    if definition_schema.get("schema_version") == 2:
        return True
    groups = definition_schema.get("groups")
    return isinstance(groups, list) and len(groups) > 0


def generate_runtime_schema(definition_schema):
    authored_schema = dict(definition_schema or {})
    if is_grouped_animal_schema(authored_schema):
        return generate_grouped_runtime_schema(authored_schema)

    dimensions = [
        dimension
        for dimension in authored_schema.get("dimensions", [])
        if isinstance(dimension, dict)
    ]
    measures = [
        normalize_measure(measure)
        for measure in authored_schema.get("measures", [])
        if isinstance(measure, dict)
    ]
    rows = generate_rows(authored_schema, dimensions)
    return {
        "schema_version": authored_schema.get("schema_version") or 1,
        "layout": "flat",
        "rows": rows,
        "measures": measures,
    }


def generate_grouped_runtime_schema(authored_schema):
    """
    Runtime shape for Option A:
    - group rows: household_quantity only
    - species rows: animal_quantity only
    - summary_fields for village / animal HH totals
    - groups[] for UI section structure
    """
    household_measure = normalize_measure(
        next(
            (
                m
                for m in authored_schema.get("group_measures", [])
                if isinstance(m, dict) and m.get("key") == "household_quantity"
            ),
            {
                "key": "household_quantity",
                "label": {"default": "Households"},
                "type": "integer",
                "required": True,
            },
        )
    )
    species_measure = normalize_measure(
        next(
            (
                m
                for m in authored_schema.get("species_measures", [])
                if isinstance(m, dict) and m.get("key") == "animal_quantity"
            ),
            next(
                (
                    m
                    for m in authored_schema.get("measures", [])
                    if isinstance(m, dict) and m.get("key") == "animal_quantity"
                ),
                {
                    "key": "animal_quantity",
                    "label": {"default": "Animal quantity"},
                    "type": "integer",
                    "required": True,
                },
            ),
        )
    )

    summary_fields = []
    for field in authored_schema.get("summary_fields") or []:
        if not isinstance(field, dict):
            continue
        summary_fields.append(
            {
                "key": field.get("key"),
                "label": label_text(field.get("label"), field.get("key")),
                "label_i18n": localized_label(field.get("label")),
                "type": field.get("type") or "integer",
                "required": field.get("required", True),
            }
        )
    if not summary_fields:
        summary_fields = [
            {
                "key": "village_household_quantity",
                "label": "HH No.",
                "label_i18n": {"default": "HH No."},
                "type": "integer",
                "required": True,
            },
            {
                "key": "animal_household_quantity",
                "label": "Animal HH No.",
                "label_i18n": {"default": "Animal HH No."},
                "type": "integer",
                "required": True,
            },
        ]

    rows = []
    groups_meta = []
    for group in authored_schema.get("groups") or []:
        if not isinstance(group, dict):
            continue
        group_key = str(group.get("key") or "").strip()
        if not group_key:
            continue
        group_label = label_text(group.get("label"), group_key)
        group_label_i18n = localized_label(group.get("label"))
        group_row_key = f"group:{group_key}"
        species_row_keys = []

        rows.append(
            {
                "key": group_row_key,
                "row_key": group_row_key,
                "row_kind": GROUP_ROW_KIND,
                "group": group_key,
                "label": group_label,
                "label_i18n": group_label_i18n,
                "dimensions": {"group": group_key},
                "measures": [household_measure],
            }
        )

        for species in group.get("species") or []:
            if not isinstance(species, dict):
                continue
            species_key = str(species.get("key") or "").strip()
            if not species_key:
                continue
            species_row_key = f"species:{species_key}"
            species_row_keys.append(species_row_key)
            species_label = label_text(species.get("label"), species_key)
            species_label_i18n = localized_label(species.get("label"))
            rows.append(
                {
                    "key": species_row_key,
                    "row_key": species_row_key,
                    "row_kind": SPECIES_ROW_KIND,
                    "group": group_key,
                    "label": species_label,
                    "label_i18n": species_label_i18n,
                    "dimensions": {"species": species_key},
                    "measures": [species_measure],
                }
            )

        groups_meta.append(
            {
                "key": group_key,
                "label": group_label,
                "label_i18n": group_label_i18n,
                "household_row_key": group_row_key,
                "species_row_keys": species_row_keys,
            }
        )

    # Union of measures for clients that only read top-level measures
    measures = [household_measure, species_measure]
    return {
        "schema_version": 2,
        "layout": "grouped_species",
        "summary_fields": summary_fields,
        "groups": groups_meta,
        "rows": rows,
        "measures": measures,
    }


def generate_rows(authored_schema, dimensions):
    if not dimensions:
        return [
            {
                "key": "row_001",
                "label": label_text(
                    authored_schema.get("display", {}).get("single_row_label"),
                    "Total",
                ),
                "label_i18n": localized_label(
                    authored_schema.get("display", {}).get("single_row_label")
                ),
                "dimensions": {},
            }
        ]

    value_lists = [dimension.get("values", []) for dimension in dimensions]
    rows = []
    for values in product(*value_lists):
        dimension_values = {
            str(dimension.get("key")): str(value.get("key"))
            for dimension, value in zip(dimensions, values)
        }
        value_labels = [
            label_text(value.get("label"), str(value.get("key"))) for value in values
        ]
        key_parts = [
            f"{dimension.get('key')}:{value.get('key')}"
            for dimension, value in zip(dimensions, values)
        ]
        row = {
            "key": "|".join(key_parts),
            "label": " / ".join(value_labels),
            "dimensions": dimension_values,
            "row_kind": SPECIES_ROW_KIND,
        }
        localized = combined_row_label(values)
        if localized:
            row["label_i18n"] = localized
        rows.append(row)
    return rows


def normalize_measure(measure):
    normalized = {
        "key": measure.get("key"),
        "label": label_text(measure.get("label"), measure.get("key")),
        "type": measure.get("type") or "integer",
        "required": measure.get("required", True),
    }
    localized = localized_label(measure.get("label"))
    if localized:
        normalized["label_i18n"] = localized
    return normalized


def runtime_schema_for_version(version):
    from census.models import CensusDefinition

    schema = dict(version.schema or {})
    if version.definition.kind != CensusDefinition.Kind.ANIMAL:
        return schema

    # Prefer regenerating from authored definition_schema when present so
    # group layout stays consistent even if stored schema is stale.
    authored = version.definition_schema
    if isinstance(authored, dict) and authored:
        schema = generate_runtime_schema(authored)

    enriched_rows = []
    for index, row in enumerate(schema.get("rows") or []):
        if not isinstance(row, dict):
            continue
        enriched_row = dict(row)
        enriched_row["row_key"] = row_key_for_row(enriched_row, index)
        enriched_rows.append(enriched_row)
    schema["rows"] = enriched_rows
    return schema


def row_key_for_row(row, index):
    return row.get("row_key") or row.get("key") or f"row_{str(index + 1).zfill(3)}"


def validate_definition_schema(definition_schema):
    errors = []
    if not isinstance(definition_schema, dict):
        return [("definition_schema", "definition schema must be an object")]

    if is_grouped_animal_schema(definition_schema):
        return validate_grouped_definition_schema(definition_schema)

    dimensions = definition_schema.get("dimensions", [])
    measures = definition_schema.get("measures", [])
    if not isinstance(dimensions, list):
        errors.append(("dimensions", "dimensions must be a list"))
        dimensions = []
    if not isinstance(measures, list) or not measures:
        errors.append(("measures", "at least one measure is required"))
        measures = []

    seen_dimensions = set()
    for dimension_index, dimension in enumerate(dimensions):
        if not isinstance(dimension, dict):
            errors.append(
                (f"dimensions.{dimension_index}", "dimension must be an object")
            )
            continue
        key = str(dimension.get("key") or "")
        if not key:
            errors.append((f"dimensions.{dimension_index}.key", "key is required"))
        elif key in seen_dimensions:
            errors.append((f"dimensions.{dimension_index}.key", "key must be unique"))
        seen_dimensions.add(key)
        values = dimension.get("values", [])
        if not isinstance(values, list) or not values:
            errors.append(
                (
                    f"dimensions.{dimension_index}.values",
                    "at least one value is required",
                )
            )
            continue
        seen_values = set()
        for value_index, value in enumerate(values):
            if not isinstance(value, dict):
                errors.append(
                    (
                        f"dimensions.{dimension_index}.values.{value_index}",
                        "value must be an object",
                    )
                )
                continue
            value_key = str(value.get("key") or "")
            if not value_key:
                errors.append(
                    (
                        f"dimensions.{dimension_index}.values.{value_index}.key",
                        "key is required",
                    )
                )
            elif value_key in seen_values:
                errors.append(
                    (
                        f"dimensions.{dimension_index}.values.{value_index}.key",
                        "key must be unique",
                    )
                )
            seen_values.add(value_key)

    errors.extend(validate_measures_list(measures, "measures"))
    return errors


def validate_grouped_definition_schema(definition_schema):
    errors = []
    groups = definition_schema.get("groups", [])
    if not isinstance(groups, list) or not groups:
        errors.append(("groups", "at least one group is required"))
        return errors

    seen_groups = set()
    seen_species = set()
    for group_index, group in enumerate(groups):
        path = f"groups.{group_index}"
        if not isinstance(group, dict):
            errors.append((path, "group must be an object"))
            continue
        group_key = str(group.get("key") or "").strip()
        if not group_key:
            errors.append((f"{path}.key", "key is required"))
        elif group_key in seen_groups:
            errors.append((f"{path}.key", "key must be unique"))
        seen_groups.add(group_key)
        if not label_text(group.get("label"), "").strip():
            errors.append((f"{path}.label", "label is required"))

        species_list = group.get("species", [])
        if not isinstance(species_list, list) or not species_list:
            errors.append((f"{path}.species", "at least one species is required"))
            continue
        for species_index, species in enumerate(species_list):
            spath = f"{path}.species.{species_index}"
            if not isinstance(species, dict):
                errors.append((spath, "species must be an object"))
                continue
            species_key = str(species.get("key") or "").strip()
            if not species_key:
                errors.append((f"{spath}.key", "key is required"))
            elif species_key in seen_species:
                errors.append((f"{spath}.key", "species key must be unique"))
            seen_species.add(species_key)
            if not label_text(species.get("label"), "").strip():
                errors.append((f"{spath}.label", "label is required"))

    species_measures = definition_schema.get("species_measures") or definition_schema.get(
        "measures"
    )
    if species_measures is not None:
        errors.extend(validate_measures_list(species_measures, "species_measures"))
    group_measures = definition_schema.get("group_measures")
    if group_measures is not None:
        errors.extend(validate_measures_list(group_measures, "group_measures"))

    return errors


def validate_measures_list(measures, field_name):
    errors = []
    if not isinstance(measures, list) or not measures:
        errors.append((field_name, "at least one measure is required"))
        return errors
    seen_measures = set()
    for measure_index, measure in enumerate(measures):
        if not isinstance(measure, dict):
            errors.append((f"{field_name}.{measure_index}", "measure must be an object"))
            continue
        key = str(measure.get("key") or "")
        if not key:
            errors.append((f"{field_name}.{measure_index}.key", "key is required"))
        elif key in seen_measures:
            errors.append((f"{field_name}.{measure_index}.key", "key must be unique"))
        seen_measures.add(key)
        if not label_text(measure.get("label"), "").strip():
            errors.append((f"{field_name}.{measure_index}.label", "label is required"))
        if (measure.get("type") or "integer") not in SUPPORTED_MEASURE_TYPES:
            errors.append(
                (f"{field_name}.{measure_index}.type", "unsupported measure type")
            )
    return errors


def localized_label(value):
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        return {"default": value}
    return None


def label_text(value, fallback):
    if isinstance(value, dict):
        return str(
            value.get("default")
            or value.get("en")
            or next(iter(value.values()), fallback)
        )
    if value is None:
        return str(fallback or "")
    return str(value)


def combined_row_label(values):
    labels = [localized_label(value.get("label")) for value in values]
    labels = [label for label in labels if label]
    if not labels:
        return None
    languages = set().union(*(label.keys() for label in labels))
    return {
        language: " / ".join(
            label.get(language) or label.get("default") or "" for label in labels
        ).strip()
        for language in languages
    }
