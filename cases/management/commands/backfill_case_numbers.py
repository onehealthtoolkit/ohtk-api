from django.core.management.base import BaseCommand, CommandError
from django_tenants.utils import get_tenant_model, schema_context

from cases.services.case_number import backfill_case_numbers


class Command(BaseCommand):
    help = "Backfill stable readable Case numbers in one explicitly selected tenant."

    def add_arguments(self, parser):
        parser.add_argument("--schema", required=True)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        schema = options["schema"]
        if not get_tenant_model().objects.filter(schema_name=schema).exists():
            raise CommandError("Tenant schema not found")
        with schema_context(schema):
            count = backfill_case_numbers(dry_run=options["dry_run"])
        action = "Would number" if options["dry_run"] else "Numbered"
        self.stdout.write(f"{action} {count} Cases in {schema}")
