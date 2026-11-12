"""Tenant-local, transactional Case numbering (D23–D28)."""
import hashlib
import re
from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError
from django.db import DEFAULT_DB_ALIAS, connections, transaction
from django.db.models import Max

LAOS_TIMEZONE = ZoneInfo("Asia/Vientiane")
MAX_SEQUENCE = 2 ** 63 - 1


def parse_case_number(value):
    """Accept a full canonical reference, with six or more sequence digits."""
    match = re.fullmatch(r"([0-9]{4})-([0-9]{6,19})", value or "")
    if not match:
        return None
    year, sequence = map(int, match.groups())
    if not (1 <= year <= 9999 and 1 <= sequence <= MAX_SEQUENCE):
        return None
    if value != f"{year:04d}-{sequence:06d}":
        return None
    return year, sequence


def lock_case_numbers(*, using=DEFAULT_DB_ALIAS):
    """Serialize creation/backfill in this tenant until the transaction commits."""
    connection = connections[using]
    if not connection.in_atomic_block:
        raise RuntimeError("Case numbering requires an atomic transaction")
    key = int.from_bytes(
        hashlib.blake2b(
            connection.schema_name.encode(), digest_size=8, person=b"case-number"
        ).digest(),
        "big",
        signed=True,
    )
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", [key])


def backfill_case_numbers(*, using=DEFAULT_DB_ALIAS, dry_run=False):
    """Assign missing numbers in original creation order, preserving existing IDs.

    Include soft-deleted rows so their numbers remain reserved. Only number fields
    are updated: UUIDs, created/updated timestamps and case status remain intact.
    Creation uses the same lock and fills any historical backlog before returning.
    """
    from cases.models import Case, CaseNumberCounter

    with transaction.atomic(using=using):
        lock_case_numbers(using=using)
        cases = Case._base_manager.using(using)
        pending = cases.filter(number_year__isnull=True).order_by("created_at", "id")
        if dry_run:
            return pending.count()
        counters = {}
        count = 0
        for case in pending.only("id", "created_at").iterator(chunk_size=500):
            if case.created_at is None:
                raise ValidationError("Case creation time is required for numbering")
            year = case.created_at.astimezone(LAOS_TIMEZONE).year
            if year not in counters:
                maximum = (
                    cases.filter(number_year=year).aggregate(
                        maximum=Max("number_sequence")
                    )["maximum"]
                    or 0
                )
                counter, _ = CaseNumberCounter.objects.using(using).get_or_create(
                    year=year, defaults={"last_number": maximum}
                )
                counter.last_number = max(counter.last_number, maximum)
                counters[year] = counter
            counter = counters[year]
            if counter.last_number >= MAX_SEQUENCE:
                raise ValidationError("Case number sequence is exhausted")
            counter.last_number += 1
            cases.filter(pk=case.pk).update(
                number_year=year, number_sequence=counter.last_number
            )
            count += 1
        for counter in counters.values():
            counter.save(using=using, update_fields=["last_number"])
        return count
