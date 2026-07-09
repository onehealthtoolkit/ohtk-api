from datetime import date

from django.db.models import Q
from django.utils import timezone

from accounts.models import Authority, AuthorityUser, Village
from census.models import (
    CensusDefinition,
    CensusRoundDefinition,
    CensusRoundOccurrence,
    VillageCensusSnapshot,
)
from common.types import AdminFieldValidationProblem


COVERAGE_MISSING = "MISSING"
COVERAGE_SUBMITTED_ON_TIME = "SUBMITTED_ON_TIME"
COVERAGE_SUBMITTED_LATE = "SUBMITTED_LATE"


def parse_month_day(value):
    if not isinstance(value, str) or len(value) != 5 or value[2] != "-":
        raise ValueError("date rule must use MM-DD")
    month = int(value[:2])
    day = int(value[3:])
    date(2000, month, day)
    return month, day


def resolve_month_day(year, value):
    month, day = parse_month_day(value)
    return date(year, month, day)


def resolve_end_date(year, start, value):
    resolved = resolve_month_day(year, value)
    if resolved < start:
        resolved = resolve_month_day(year + 1, value)
    return resolved


def resolve_definition_dates(definition, year):
    start_date = resolve_month_day(year, definition.start_date)
    soft_finish_date = resolve_end_date(year, start_date, definition.soft_finish_date)
    hard_finish_date = resolve_end_date(year, start_date, definition.hard_finish_date)
    census_period_start = resolve_month_day(year, definition.census_period_start)
    census_period_end = resolve_end_date(
        year, census_period_start, definition.census_period_end
    )
    return {
        "census_period_start": census_period_start,
        "census_period_end": census_period_end,
        "start_date": start_date,
        "soft_finish_date": soft_finish_date,
        "hard_finish_date": hard_finish_date,
    }


def validate_round_definition(definition):
    errors = []
    for field in (
        "census_period_start",
        "census_period_end",
        "start_date",
        "soft_finish_date",
        "hard_finish_date",
    ):
        try:
            parse_month_day(getattr(definition, field))
        except (TypeError, ValueError):
            errors.append((field, "date rule must use valid MM-DD"))

    if errors:
        return errors

    dates = resolve_definition_dates(definition, 2026)
    if dates["soft_finish_date"] < dates["start_date"]:
        errors.append(("soft_finish_date", "soft finish must be on or after start"))
    if dates["hard_finish_date"] < dates["soft_finish_date"]:
        errors.append(
            ("hard_finish_date", "hard finish must be on or after soft finish")
        )
    if dates["census_period_end"] < dates["census_period_start"]:
        errors.append(
            ("census_period_end", "census period end must be on or after start")
        )
    return errors


def materialize_occurrence(definition, year):
    dates = resolve_definition_dates(definition, year)
    occurrence_key = f"{definition.code}_{year}"
    occurrence, _created = CensusRoundOccurrence.objects.update_or_create(
        definition=definition,
        year=year,
        defaults={
            "occurrence_key": occurrence_key,
            "kind": definition.kind,
            "mode": definition.mode,
            "target_authority": definition.target_authority,
            **dates,
        },
    )
    return occurrence


def materialize_occurrences(definition, start_year, years=2):
    return [
        materialize_occurrence(definition, year)
        for year in range(start_year, start_year + years)
    ]


def occurrence_includes_village(occurrence, village):
    target_authority = occurrence.target_authority
    if target_authority is None:
        return True
    return target_authority.is_in_inherits_down([village.authority_id])


def occurrence_is_open_for_date(occurrence, submitted_date):
    return occurrence.start_date <= submitted_date <= occurrence.hard_finish_date


def occurrence_submission_status(occurrence, submitted_date):
    if submitted_date <= occurrence.soft_finish_date:
        return COVERAGE_SUBMITTED_ON_TIME
    return COVERAGE_SUBMITTED_LATE


def resolve_submission_occurrence(
    occurrence_id, census_date, definition_version, village, problems
):
    if definition_version is None or village is None:
        return None, None

    if occurrence_id is not None:
        try:
            occurrence = CensusRoundOccurrence.objects.select_related(
                "definition", "target_authority"
            ).get(pk=occurrence_id)
        except CensusRoundOccurrence.DoesNotExist:
            problems.append(
                AdminFieldValidationProblem(
                    name="occurrence_id",
                    message="census round occurrence does not exist",
                )
            )
            return None, None
        resolution = VillageCensusSnapshot.RoundResolution.EXPLICIT
    else:
        occurrences = list(
            CensusRoundOccurrence.objects.select_related(
                "definition", "target_authority"
            ).filter(
                kind=definition_version.definition.kind,
                mode=CensusRoundDefinition.Mode.PRODUCTION,
                definition__enabled=True,
                start_date__lte=census_date,
                hard_finish_date__gte=census_date,
            )
        )
        occurrences = [
            occurrence
            for occurrence in occurrences
            if occurrence_includes_village(occurrence, village)
        ]
        if len(occurrences) == 1:
            occurrence = occurrences[0]
            resolution = VillageCensusSnapshot.RoundResolution.INFERRED
        elif len(occurrences) > 1:
            problems.append(
                AdminFieldValidationProblem(
                    name="occurrence_id",
                    message="multiple open census rounds match; occurrence is required",
                )
            )
            return None, None
        else:
            problems.append(
                AdminFieldValidationProblem(
                    name="occurrence_id",
                    message="open census round occurrence is required",
                )
            )
            return None, None

    validate_submission_occurrence(occurrence, census_date, definition_version, village, problems)
    if problems:
        return None, None
    return occurrence, resolution


def validate_submission_occurrence(
    occurrence, census_date, definition_version, village, problems
):
    if occurrence.kind != definition_version.definition.kind:
        problems.append(
            AdminFieldValidationProblem(
                name="occurrence_id",
                message="census round kind does not match definition",
            )
        )
    if not occurrence_includes_village(occurrence, village):
        problems.append(
            AdminFieldValidationProblem(
                name="occurrence_id",
                message="village is outside census round target scope",
            )
        )
    if not occurrence_is_open_for_date(occurrence, census_date):
        problems.append(
            AdminFieldValidationProblem(
                name="occurrence_id",
                message="census round is not open for submitted census date",
            )
        )


def available_occurrences_for_village(village, kind, mode=None, as_of=None):
    if as_of is None:
        as_of = timezone.localdate()
    queryset = CensusRoundOccurrence.objects.select_related(
        "definition", "target_authority"
    ).filter(
        kind=kind,
        definition__enabled=True,
        start_date__lte=as_of,
        hard_finish_date__gte=as_of,
    )
    if mode:
        queryset = queryset.filter(mode=mode)
    return [
        occurrence
        for occurrence in queryset.order_by("start_date", "occurrence_key")
        if occurrence_includes_village(occurrence, village)
    ]


def permitted_villages_for_coverage(user, authority_id=None):
    queryset = Village.objects.filter(active=True).select_related("authority")
    if authority_id is not None:
        try:
            target_authority = Authority.objects.get(pk=int(authority_id))
        except (Authority.DoesNotExist, TypeError, ValueError):
            return Village.objects.none()
        queryset = queryset.filter(
            authority__in=target_authority.all_inherits_down()
        )

    if user.is_superuser:
        return queryset
    if user.is_authority_role_in([AuthorityUser.Role.ADMIN]):
        return queryset.filter(
            authority__in=user.authorityuser.authority.all_inherits_down()
        )
    if user.is_authority_role_in([AuthorityUser.Role.OFFICER]):
        return queryset.filter(authority=user.authorityuser.authority)
    return None


def build_coverage(occurrence, user, authority_id=None, status=None, q=None):
    villages = permitted_villages_for_coverage(user, authority_id)
    if villages is None:
        return None
    if occurrence.target_authority_id is not None:
        villages = villages.filter(
            authority__in=occurrence.target_authority.all_inherits_down()
        )
    if q:
        villages = villages.filter(Q(name__icontains=q) | Q(code__icontains=q))

    village_list = list(villages.order_by("authority__name", "code", "name"))
    snapshots = (
        VillageCensusSnapshot.objects.filter(round_occurrence=occurrence)
        .select_related("village", "reporter", "round_occurrence")
        .prefetch_related("facts")
        .order_by("village_id", "-submitted_at", "-id")
    )
    snapshot_by_village_id = {}
    for snapshot in snapshots:
        snapshot_by_village_id.setdefault(snapshot.village_id, snapshot)

    rows = []
    submitted_count = 0
    late_count = 0
    for village in village_list:
        snapshot = snapshot_by_village_id.get(village.id)
        row_status = COVERAGE_MISSING
        if snapshot is not None:
            submitted_count += 1
            row_status = occurrence_submission_status(occurrence, snapshot.census_date)
            if row_status == COVERAGE_SUBMITTED_LATE:
                late_count += 1

        if status and status != "ALL" and row_status != status:
            continue

        rows.append(
            {
                "village": village,
                "occurrence": occurrence,
                "snapshot": snapshot,
                "status": row_status,
                "total_animal_quantity": total_animal_quantity(snapshot),
                "species_summary": species_summary(snapshot),
            }
        )

    missing_count = len(village_list) - submitted_count
    return {
        "total_count": len(rows),
        "submitted_count": submitted_count,
        "missing_count": missing_count,
        "late_count": late_count,
        "rows": rows,
    }


def total_animal_quantity(snapshot):
    if snapshot is None:
        return None
    total = 0
    for fact in snapshot.facts.all():
        value = (fact.measures or {}).get("animal_quantity")
        if isinstance(value, int) and not isinstance(value, bool):
            total += value
    return total


def species_summary(snapshot):
    if snapshot is None:
        return []
    summary = []
    for fact in snapshot.facts.all():
        value = (fact.measures or {}).get("animal_quantity")
        if not isinstance(value, int) or isinstance(value, bool):
            value = 0
        summary.append(
            {
                "row_key": fact.row_key,
                "row_label": fact.row_label,
                "animal_quantity": value,
            }
        )
    return summary
