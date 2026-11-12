from datetime import datetime, timezone
from io import StringIO
from unittest.mock import patch
from uuid import UUID

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.test import TestCase

from cases.models import Case, CaseNumberCounter
from cases.services.case_number import backfill_case_numbers, parse_case_number


def instant(year, month=1, day=1, hour=0, minute=0):
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


def legacy_case(created_at, **kwargs):
    """Emulate rows present before migration (bulk insert skips model.save)."""
    case = Case(**kwargs)
    Case.objects.bulk_create([case])
    Case.objects.filter(pk=case.pk).update(created_at=created_at)
    case.refresh_from_db()
    return case


class CaseNumberTests(TestCase):
    def create_at(self, timestamp, **kwargs):
        with patch("django.utils.timezone.now", return_value=timestamp):
            return Case.objects.create(**kwargs)

    def test_laos_new_year_resets_sequence_and_keeps_old_reference(self):
        first = self.create_at(instant(2026, 12, 31, 16, 59))
        second = self.create_at(instant(2026, 12, 31, 17))
        third = self.create_at(instant(2027))
        self.assertEqual(first.case_number, "2026-000001")
        self.assertEqual(second.case_number, "2027-000001")
        self.assertEqual(third.case_number, "2027-000002")
        first.description = "edited next year"
        first.is_finished = True
        first.save()
        first.refresh_from_db()
        self.assertEqual(first.case_number, "2026-000001")
        self.assertEqual(first.created_at, instant(2026, 12, 31, 16, 59))

    def test_sequence_grows_past_six_digits_without_truncation(self):
        CaseNumberCounter.objects.create(year=2026, last_number=999999)
        case = self.create_at(instant(2026))
        self.assertEqual(case.case_number, "2026-1000000")

    def test_exhausted_sequence_rolls_back_new_case(self):
        CaseNumberCounter.objects.create(year=2026, last_number=2 ** 63 - 1)
        with self.assertRaises(ValidationError):
            self.create_at(instant(2026))
        self.assertFalse(Case.objects.exists())

    def test_number_is_immutable_and_not_caller_supplied(self):
        with self.assertRaises(ValidationError):
            Case.objects.create(number_year=2026, number_sequence=10)
        case = self.create_at(instant(2026))
        case.number_sequence = 10
        with self.assertRaises(ValidationError):
            case.save()
        with self.assertRaises(ValidationError):
            case.save(update_fields=["number_sequence"])

    def test_soft_deleted_numbers_are_reserved(self):
        first = self.create_at(instant(2026))
        first.delete()
        second = self.create_at(instant(2026))
        self.assertEqual(second.case_number, "2026-000002")

    def test_rollback_does_not_commit_case_or_counter(self):
        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                self.create_at(instant(2026))
                raise RuntimeError("promotion failed")
        self.assertFalse(Case.objects.exists())
        self.assertFalse(CaseNumberCounter.objects.exists())
        self.assertEqual(self.create_at(instant(2026)).case_number, "2026-000001")

    def test_database_rejects_duplicate_incomplete_or_nonpositive_numbers(self):
        case = self.create_at(instant(2026))
        other = self.create_at(instant(2026))
        for values in (
            dict(number_year=2026, number_sequence=case.number_sequence),
            dict(number_year=2026, number_sequence=None),
            dict(number_year=None, number_sequence=1),
            dict(number_year=0, number_sequence=1),
            dict(number_year=10000, number_sequence=1),
            dict(number_year=2026, number_sequence=0),
        ):
            with self.subTest(values=values), self.assertRaises(IntegrityError):
                with transaction.atomic():
                    Case.objects.filter(pk=other.pk).update(**values)

    def test_backfill_open_closed_and_ties_preserves_other_fields_and_reruns(self):
        later = legacy_case(instant(2026, 2), is_finished=True)
        tie_second = legacy_case(instant(2026), id=UUID(int=2))
        tie_first = legacy_case(instant(2026), id=UUID(int=1))
        old_year = legacy_case(instant(2025, 12, 31, 16, 59))
        laos_new_year = legacy_case(instant(2025, 12, 31, 17))
        deleted = legacy_case(instant(2026, 3), deleted_at=instant(2026, 4))
        snapshots = {
            item.pk: (
                item.created_at,
                item.updated_at,
                item.is_finished,
                item.deleted_at,
            )
            for item in Case._base_manager.all()
        }
        self.assertEqual(backfill_case_numbers(dry_run=True), 6)
        self.assertFalse(CaseNumberCounter.objects.exists())
        self.assertFalse(Case.objects.filter(number_year__isnull=False).exists())
        self.assertEqual(backfill_case_numbers(), 6)
        for case, expected in (
            (old_year, "2025-000001"),
            (laos_new_year, "2026-000001"),
            (tie_first, "2026-000002"),
            (tie_second, "2026-000003"),
            (later, "2026-000004"),
            (deleted, "2026-000005"),
        ):
            case.refresh_from_db()
            self.assertEqual(case.case_number, expected)
            self.assertEqual(
                (case.created_at, case.updated_at, case.is_finished, case.deleted_at),
                snapshots[case.pk],
            )
        self.assertEqual(backfill_case_numbers(), 0)
        self.assertEqual(backfill_case_numbers(dry_run=True), 0)

    def test_new_creation_drains_historical_backlog_first(self):
        old = legacy_case(instant(2026))
        new = self.create_at(instant(2026, 3))
        old.refresh_from_db()
        self.assertEqual(old.case_number, "2026-000001")
        self.assertEqual(new.case_number, "2026-000002")

    def test_backfill_keeps_existing_numbers_and_reconciles_stale_counter(self):
        existing = legacy_case(instant(2026), number_year=2026, number_sequence=8)
        old = legacy_case(instant(2026, 2))
        CaseNumberCounter.objects.create(year=2026, last_number=2)
        backfill_case_numbers()
        existing.refresh_from_db()
        old.refresh_from_db()
        self.assertEqual(existing.case_number, "2026-000008")
        self.assertEqual(old.case_number, "2026-000009")
        self.assertEqual(CaseNumberCounter.objects.get(pk=2026).last_number, 9)

    def test_stale_instance_does_not_erase_backfilled_number(self):
        case = legacy_case(instant(2026))
        backfill_case_numbers()
        case.description = "stale instance edit"
        case.save()
        case.refresh_from_db()
        self.assertEqual(case.case_number, "2026-000001")
        self.assertEqual(case.description, "stale instance edit")

    def test_full_reference_parser_accepts_only_valid_canonical_numbers(self):
        for text, expected in (
            ("2026-000001", (2026, 1)),
            ("2026-1000000", (2026, 1000000)),
            ("2026-000000", None),
            ("0000-000001", None),
            ("2026-1", None),
            ("2026-0000001", None),
            ("2026-9223372036854775808", None),
            ("2569/000001", None),
        ):
            with self.subTest(text=text):
                self.assertEqual(parse_case_number(text), expected)

    def test_backfill_command_requires_explicit_existing_tenant(self):
        with self.assertRaises(CommandError):
            call_command("backfill_case_numbers", stdout=StringIO())
        with self.assertRaises(CommandError):
            call_command("backfill_case_numbers", schema="missing", stdout=StringIO())
