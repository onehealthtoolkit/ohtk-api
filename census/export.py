"""
Census round Excel export helpers.

Layout:
  - Rows: villages (scoped by authority hierarchy permission)
  - Leading columns: authority hierarchy levels (root → leaf) + village identity
  - Metric columns: household totals, total animals, then one column per species/row_key
"""

from accounts.models import Authority
from census.rounds import build_coverage, species_summary


def authority_hierarchy_path(authority):
    """
    Return authority names from root parent down to the village's authority.

    Walks the inherits M2M (child.inherits → parent). Multiple parents are rare;
    the first parent is used when present.
    """
    if authority is None:
        return []
    chain = []
    current = authority
    seen = set()
    while current is not None and current.id not in seen:
        seen.add(current.id)
        chain.append(current)
        parents = list(current.inherits.all())
        current = parents[0] if parents else None
    chain.reverse()
    return chain


def _summary_quantity(snapshot, key):
    if snapshot is None:
        return None
    summary = (snapshot.form_data or {}).get("summary") or {}
    value = summary.get(key)
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def collect_species_columns(coverage_rows):
    """Stable ordered list of (row_key, row_label) for species metric columns."""
    columns = []
    seen = set()
    for row in coverage_rows:
        for item in row.get("species_summary") or []:
            key = item.get("row_key") or item.get("rowKey")
            if not key or key in seen:
                continue
            if str(key).startswith("group:"):
                continue
            seen.add(key)
            label = item.get("row_label") or item.get("rowLabel") or key
            columns.append((key, label))
    return columns


def build_export_table(occurrence, user, authority_id=None):
    """
    Build headers + data rows for a census round export.

    Returns:
      {
        "title": str,
        "occurrence_key": str,
        "authority_name": str | None,
        "headers": [str, ...],
        "rows": [[cell, ...], ...],
      }
    or None when the user has no permission.
    """
    coverage = build_coverage(
        occurrence, user, authority_id=authority_id, status="ALL"
    )
    if coverage is None:
        return None

    coverage_rows = coverage["rows"]
    hierarchy_paths = [
        authority_hierarchy_path(row["village"].authority) for row in coverage_rows
    ]
    max_depth = max((len(path) for path in hierarchy_paths), default=0)
    # At least one hierarchy column so the sheet stays readable when empty.
    hierarchy_depth = max(max_depth, 1)

    species_columns = collect_species_columns(coverage_rows)

    headers = []
    for index in range(hierarchy_depth):
        headers.append(f"Authority L{index + 1}")
    headers.extend(
        [
            "Village code",
            "Village name",
            "Status",
            "Census date",
            "Submitted at",
            "Reporter",
            "Village households",
            "Households with animals",
            "Total animals",
        ]
    )
    for _key, label in species_columns:
        headers.append(label)

    data_rows = []
    for row, path in zip(coverage_rows, hierarchy_paths):
        village = row["village"]
        snapshot = row.get("snapshot")
        species_map = {
            (item.get("row_key") or item.get("rowKey")): item.get(
                "animal_quantity", item.get("animalQuantity")
            )
            for item in (row.get("species_summary") or [])
        }

        cells = []
        for index in range(hierarchy_depth):
            cells.append(path[index].name if index < len(path) else "")
        cells.extend(
            [
                village.code,
                village.name,
                row.get("status") or "",
                str(snapshot.census_date) if snapshot and snapshot.census_date else "",
                (
                    snapshot.submitted_at.isoformat()
                    if snapshot and snapshot.submitted_at
                    else ""
                ),
                (
                    snapshot.reporter.username
                    if snapshot and snapshot.reporter_id
                    else ""
                ),
                _summary_quantity(snapshot, "village_household_quantity"),
                _summary_quantity(snapshot, "animal_household_quantity"),
                row.get("total_animal_quantity"),
            ]
        )
        for key, _label in species_columns:
            cells.append(species_map.get(key))
        data_rows.append(cells)

    authority_name = None
    if authority_id is not None:
        try:
            authority_name = Authority.objects.get(pk=int(authority_id)).name
        except (Authority.DoesNotExist, TypeError, ValueError):
            authority_name = None
    elif user is not None and getattr(user, "is_authority_user", False):
        authority_name = user.authorityuser.authority.name

    return {
        "title": f"Census round {occurrence.occurrence_key}",
        "occurrence_key": occurrence.occurrence_key,
        "authority_name": authority_name,
        "headers": headers,
        "rows": data_rows,
        "total_count": coverage["total_count"],
        "submitted_count": coverage["submitted_count"],
        "missing_count": coverage["missing_count"],
        "late_count": coverage["late_count"],
    }
