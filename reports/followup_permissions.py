from accounts.models import AuthorityUser, VillageReporterAssignment
from accounts.village_capability import is_village_capability_enabled


def has_followup_permission(user, incident):
    """Check the actor's village scope, independently of report-type settings."""
    if not user.is_authenticated:
        return False
    if user.is_superuser or not user.is_authority_role_in(
        [AuthorityUser.Role.REPORTER]
    ):
        return True
    if not is_village_capability_enabled():
        return True
    if incident.village_id is None:
        return False

    return VillageReporterAssignment.objects.filter(
        reporter_id=user.pk,
        village_id=incident.village_id,
        village__active=True,
        village__deleted_at__isnull=True,
    ).exists()
