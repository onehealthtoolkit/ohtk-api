from itertools import product


SUPPORTED_MEASURE_TYPES = {"integer"}


def generate_runtime_schema(definition_schema):
    authored_schema = dict(definition_schema or {})
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

    seen_measures = set()
    for measure_index, measure in enumerate(measures):
        if not isinstance(measure, dict):
            errors.append((f"measures.{measure_index}", "measure must be an object"))
            continue
        key = str(measure.get("key") or "")
        if not key:
            errors.append((f"measures.{measure_index}.key", "key is required"))
        elif key in seen_measures:
            errors.append((f"measures.{measure_index}.key", "key must be unique"))
        seen_measures.add(key)
        if not label_text(measure.get("label"), "").strip():
            errors.append((f"measures.{measure_index}.label", "label is required"))
        if (measure.get("type") or "integer") not in SUPPORTED_MEASURE_TYPES:
            errors.append(
                (f"measures.{measure_index}.type", "unsupported measure type")
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
