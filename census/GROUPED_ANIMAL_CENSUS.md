# Grouped animal census (Option A)

## Model

- **Group rows** (`row_key` = `group:<KEY>`): store only `household_quantity`
  - Includes **Pig** as `group:PIG` (HH is not on `species:PIG`)
- **Species rows** (`row_key` = `species:<KEY>`): store only `animal_quantity`
- **Summary**: `village_household_quantity`, `animal_household_quantity`
- **Date**: snapshot `census_date`

## Authored schema

`schema_version: 2` with `groups[]`, `group_measures`, `species_measures`, `summary_fields`.

Legacy `schema_version: 1` with `dimensions` + dual measures per species row remains supported.

## Runtime

`generate_runtime_schema` emits `layout: "grouped_species"`, `groups` UI metadata, and per-row `measures`.

## Submit validation

- Per-row required measures
- Group HH ≤ animal HH
- Heads > 0 ⇒ group HH ≥ 1
- Group HH = 0 ⇒ heads in group = 0
