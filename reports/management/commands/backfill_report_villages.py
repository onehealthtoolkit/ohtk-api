"""
Backfill IncidentReport.village for reports that lack it.

Strategies (in order, first match wins):
1. Exact GPS match to a Village.location under the report's relevant authorities
   (rounded to 5 decimals — same as gps_location_str).
2. If the report has exactly one relevant authority and that authority has
   exactly one active village with a location, use it.

Usage (tenant schema):
  python manage.py backfill_report_villages --schema demo --dry-run
  python manage.py backfill_report_villages --schema demo
"""

from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand
from django_tenants.utils import get_tenant_model, schema_context

from accounts.models import Village
from reports.models.report import IncidentReport


class Command(BaseCommand):
    help = "Backfill IncidentReport.village from GPS or single-village authority"

    def add_arguments(self, parser):
        parser.add_argument(
            "--schema",
            type=str,
            default=None,
            help="Tenant schema name (default: all non-public tenants)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print matches without saving",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        schema = options["schema"]
        Tenant = get_tenant_model()
        if schema:
            schemas = [schema]
        else:
            schemas = list(
                Tenant.objects.exclude(schema_name="public").values_list(
                    "schema_name", flat=True
                )
            )

        total_updated = 0
        for schema_name in schemas:
            with schema_context(schema_name):
                n = self._backfill_schema(schema_name, dry_run)
                total_updated += n
        self.stdout.write(
            self.style.SUCCESS(
                f"{'Would update' if dry_run else 'Updated'} {total_updated} report(s)"
            )
        )

    def _backfill_schema(self, schema_name: str, dry_run: bool) -> int:
        qs = (
            IncidentReport.objects.filter(village__isnull=True)
            .prefetch_related("relevant_authorities")
            .order_by("created_at")
        )
        updated = 0
        for report in qs.iterator(chunk_size=100):
            village = self._match_village(report)
            if village is None:
                continue
            updated += 1
            self.stdout.write(
                f"[{schema_name}] report {report.id} -> village "
                f"{village.id} {village.code or ''} {village.name}"
            )
            if not dry_run:
                IncidentReport.objects.filter(pk=report.pk).update(village_id=village.id)
        return updated

    def _match_village(self, report: IncidentReport):
        authority_ids = list(report.relevant_authorities.values_list("id", flat=True))
        if not authority_ids:
            return None

        villages = Village.objects.filter(
            authority_id__in=authority_ids, active=True
        )
        if not villages.exists():
            return None

        # 1) GPS exact-ish match
        if report.gps_location:
            pt: Point = report.gps_location
            for v in villages.exclude(location__isnull=True):
                if v.location is None:
                    continue
                if (
                    round(v.location.x, 5) == round(pt.x, 5)
                    and round(v.location.y, 5) == round(pt.y, 5)
                ):
                    return v
            # nearest within ~200m (0.002 deg ~ 200m)
            nearest = (
                villages.exclude(location__isnull=True)
                .annotate(dist=Distance("location", pt))
                .order_by("dist")
                .first()
            )
            if nearest is not None and nearest.location is not None:
                # Distance in degrees for geographic; use meter if geography
                try:
                    dist_m = nearest.dist.m  # type: ignore[attr-defined]
                except Exception:
                    dist_m = float(nearest.dist) * 111_000  # rough deg->m
                if dist_m <= 250:
                    return nearest

        # 2) Single village under single authority
        if len(authority_ids) == 1:
            under = list(villages.filter(authority_id=authority_ids[0])[:2])
            if len(under) == 1:
                return under[0]

        return None
