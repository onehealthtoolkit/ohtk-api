from concurrent.futures import ThreadPoolExecutor
from datetime import date
from io import StringIO
from threading import Barrier
from unittest.mock import patch

from django.core.management import call_command
from django.db import connection, connections
from django_tenants.test.cases import TenantTestCase
from django_tenants.utils import schema_context

from accounts.models import Authority, AuthorityUser
from cases.models import Case, CaseNumberCounter, StateDefinition, StateStep
from cases.services.case_number import backfill_case_numbers
from cases.tests.test_case_number import instant, legacy_case
from reports.models import Category, IncidentReport, ReportType
from tenants.models import Client


class CaseNumberConcurrencyTests(TenantTestCase):
    """Real committed transactions, each worker owns a PostgreSQL connection."""

    @classmethod
    def _fixture_setup(cls):
        pass  # TenantTestCase owns the temporary schema; avoid TestCase's atomic.

    def _fixture_teardown(self):
        pass

    def setUp(self):
        Case._base_manager.all().delete()
        CaseNumberCounter.objects.all().delete()

    def run_parallel(self, operations):
        barrier = Barrier(len(operations))
        tenant_schema = self.tenant.schema_name

        def worker(operation):
            try:
                with schema_context(tenant_schema):
                    with connection.cursor() as cursor:
                        cursor.execute("SET statement_timeout = '10s'")
                    barrier.wait(timeout=10)
                    return operation()
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=len(operations)) as pool:
            futures = [pool.submit(worker, operation) for operation in operations]
            return [future.result(timeout=20) for future in futures]

    def test_concurrent_creation_backfill_and_duplicate_promotion(self):
        old = legacy_case(instant(2020))
        operations = [lambda: Case.objects.create().pk for _ in range(6)]
        operations.append(lambda: backfill_case_numbers())
        self.run_parallel(operations)
        rows = list(Case.objects.all())
        self.assertEqual(len(rows), 7)
        self.assertEqual(len({row.case_number for row in rows}), 7)
        self.assertTrue(all(row.case_number for row in rows))
        old.refresh_from_db()
        self.assertEqual(old.case_number, "2020-000001")
        current = [row.number_sequence for row in rows if row.pk != old.pk]
        self.assertEqual(sorted(current), list(range(1, 7)))

        authority = Authority.objects.create(code="A", name="A")
        user = AuthorityUser.objects.create(username="number-test", authority=authority)
        report_type = ReportType.objects.create(
            name="Number test",
            definition={},
            category=Category.objects.create(name="Animals"),
        )
        definition = StateDefinition.objects.create(name="Default", is_default=True)
        StateStep.objects.create(
            name="Open", state_definition=definition, is_start_state=True
        )
        report = IncidentReport.objects.create(
            reported_by=user,
            report_type=report_type,
            data={},
            incident_date=date(2000, 1, 1),
            relevant_authority_resolved=True,
        )
        report.relevant_authorities.add(authority)
        with patch("cases.signals.case_promoted.send"):
            ids = self.run_parallel(
                [
                    lambda: Case.promote_from_incident_report(report.pk).pk
                    for _ in range(3)
                ]
            )
        self.assertEqual(len(set(ids)), 1)
        self.assertEqual(Case.objects.filter(report=report).count(), 1)
        report.refresh_from_db()
        self.assertEqual(report.case_id, ids[0])

    def test_tenant_counter_and_command_are_isolated(self):
        tenant_case = legacy_case(instant(2021))
        other = Client(schema_name="case_numbers_other", name="Other")
        with schema_context("public"):
            other.save(verbosity=0)
        try:
            with schema_context(other.schema_name):
                foreign = legacy_case(instant(2021))
            output = StringIO()
            call_command(
                "backfill_case_numbers",
                schema=self.tenant.schema_name,
                dry_run=True,
                stdout=output,
            )
            self.assertIn("Would number 1 Cases", output.getvalue())
            tenant_case.refresh_from_db()
            self.assertIsNone(tenant_case.case_number)
            call_command(
                "backfill_case_numbers",
                schema=self.tenant.schema_name,
                stdout=StringIO(),
            )
            tenant_case.refresh_from_db()
            self.assertEqual(tenant_case.case_number, "2021-000001")
            with schema_context(other.schema_name):
                foreign.refresh_from_db()
                self.assertIsNone(foreign.case_number)
                self.assertFalse(CaseNumberCounter.objects.exists())
                backfill_case_numbers()
                foreign.refresh_from_db()
                self.assertEqual(foreign.case_number, tenant_case.case_number)
                with patch("django.utils.timezone.now", return_value=instant(2021, 3)):
                    self.assertEqual(Case.objects.create().case_number, "2021-000002")
            # Same tenant, different authorities still share one sequence.
            a = Authority.objects.create(code="B", name="B")
            b = Authority.objects.create(code="C", name="C")
            with patch("django.utils.timezone.now", return_value=instant(2021, 3)):
                second = Case.objects.create()
                second.authorities.add(a)
                third = Case.objects.create()
                third.authorities.add(b)
            self.assertEqual(second.case_number, "2021-000002")
            self.assertEqual(third.case_number, "2021-000003")
        finally:
            with schema_context("public"):
                other.delete(force_drop=True)
