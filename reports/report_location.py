from typing import Optional

from django.contrib.gis.geos import Point

from accounts.models import AuthorityUser, VillageReporterAssignment
from accounts.report_location_fallback import (
    is_report_use_village_location_fallback_enabled,
)


def parse_client_gps_location(gps_location: Optional[str]) -> Optional[Point]:
    """Parse client gps string as longitude,latitude (existing submit contract)."""
    if gps_location is None:
        return None
    text = str(gps_location).strip()
    if not text:
        return None
    parts = text.split(",")
    if len(parts) != 2:
        raise ValueError("gps_location must be 'longitude,latitude'")
    longitude = float(parts[0].strip())
    latitude = float(parts[1].strip())
    return Point(longitude, latitude)


def get_reporter_village_location_point(user) -> Optional[Point]:
    """
    Deterministic village fallback: lowest village_id among active assignments
    that have a non-null village.location.
    """
    reporter = user
    if not isinstance(reporter, AuthorityUser):
        if getattr(user, "is_authority_user", False):
            reporter = user.authorityuser
        else:
            return None

    assignment = (
        VillageReporterAssignment.objects.filter(
            reporter=reporter,
            village__active=True,
            village__location__isnull=False,
        )
        .select_related("village")
        .order_by("village_id")
        .first()
    )
    if assignment is None:
        return None
    return assignment.village.location


def resolve_incident_report_gps(user, gps_location: Optional[str]) -> Optional[Point]:
    """
    1. Client GPS if provided
    2. Else village location if features.report_use_village_location_fallback=enable
    3. Else None
    """
    client_point = parse_client_gps_location(gps_location)
    if client_point is not None:
        return client_point

    if not is_report_use_village_location_fallback_enabled():
        return None

    return get_reporter_village_location_point(user)
