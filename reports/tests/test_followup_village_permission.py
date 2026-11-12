import uuid

from django.utils.timezone import now
from graphql_jwt.testcases import JSONWebTokenClient

from accounts.models import (
    AuthorityUser,
    Configuration,
    Village,
    VillageReporterAssignment,
)
from accounts.village_capability import (
    VILLAGE_CAPABILITY_KEY,
    set_village_capability_enabled,
)
from reports.models import IncidentReport
from reports.models.report import FollowUpReport
from reports.tests.base_testcase import BaseTestCase


class FollowupVillagePermissionTestCase(BaseTestCase):
    client_class = JSONWebTokenClient

    def setUp(self):
        super().setUp()
        set_village_capability_enabled(True)
        self.client.authenticate(self.jatujak_reporter)
        self.village = Village.objects.create(
            authority=self.jatujak, code="assigned", name="Assigned village"
        )
        self.other_village = Village.objects.create(
            authority=self.jatujak, code="other", name="Other village"
        )
        self.assignment = VillageReporterAssignment.objects.create(
            reporter=self.jatujak_reporter,
            village=self.village,
            census_role=VillageReporterAssignment.CensusRole.VOLUNTEER,
        )
        # The incident author is deliberately a different user.
        self.report = IncidentReport.objects.create(
            reported_by=self.user,
            incident_date=now(),
            report_type=self.mers_report_type,
            village=self.village,
            data={"symptom": "cough", "number_of_sick": 1},
        )

    def assert_followup_permission(self, allowed):
        result = self.client.execute(
            """query permission($id: ID!) {
                incidentReport(id: $id) { hasFollowupPermission }
            }""",
            {"id": str(self.report.id)},
        )
        self.assertIsNone(result.errors, msg=result.errors)
        self.assertEqual(
            result.data["incidentReport"]["hasFollowupPermission"], allowed
        )
        self.assert_submit_permission(allowed)

    def assert_submit_permission(self, allowed):
        followup_id = uuid.uuid4()
        result = self.client.execute(
            """mutation submit($id: UUID!, $followupId: UUID!, $data: GenericScalar!) {
                submitFollowupReport(
                    incidentId: $id, followupId: $followupId, data: $data
                ) { result { id } }
            }""",
            {
                "id": str(self.report.id),
                "followupId": str(followup_id),
                "data": {"condition": "better"},
            },
        )
        if allowed:
            self.assertIsNone(result.errors, msg=result.errors)
            self.assertEqual(
                result.data["submitFollowupReport"]["result"]["id"],
                str(followup_id),
            )
        else:
            self.assertTrue(result.errors)
            self.assertIn("village is not assigned to reporter", str(result.errors))
        self.assertEqual(FollowUpReport.objects.filter(id=followup_id).exists(), allowed)

    def test_reporter_can_followup_another_authors_report_in_assigned_village(self):
        self.assert_followup_permission(True)

    def test_direct_mutation_denies_unassigned_village(self):
        self.report.village = self.other_village
        self.report.save(update_fields=["village"])
        self.assert_submit_permission(False)

    def test_reporter_cannot_followup_unassigned_village_even_for_own_report(self):
        self.report.village = self.other_village
        self.report.reported_by = self.jatujak_reporter
        self.report.save(update_fields=["village", "reported_by"])
        self.assert_followup_permission(False)

    def test_another_reporters_assignment_does_not_grant_permission(self):
        self.assignment.delete()
        VillageReporterAssignment.objects.create(
            reporter=self.user, village=self.village
        )
        self.assert_followup_permission(False)

    def test_deleted_assignment_does_not_grant_permission(self):
        self.assignment.delete()
        self.assert_followup_permission(False)

    def test_assignment_revoked_after_detail_load_is_checked_on_submit(self):
        result = self.client.execute(
            """query permission($id: ID!) {
                incidentReport(id: $id) { hasFollowupPermission }
            }""",
            {"id": str(self.report.id)},
        )
        self.assertIsNone(result.errors, msg=result.errors)
        self.assertTrue(result.data["incidentReport"]["hasFollowupPermission"])
        self.assignment.delete()
        self.assert_submit_permission(False)

    def test_all_assigned_villages_are_allowed(self):
        VillageReporterAssignment.objects.create(
            reporter=self.jatujak_reporter, village=self.other_village
        )
        self.report.village = self.other_village
        self.report.save(update_fields=["village"])
        self.assert_followup_permission(True)

    def test_census_official_assignment_also_grants_followup_permission(self):
        self.assignment.census_role = VillageReporterAssignment.CensusRole.OFFICIAL
        self.assignment.save(update_fields=["census_role"])
        self.assert_followup_permission(True)

    def test_inactive_village_does_not_grant_permission(self):
        self.village.active = False
        self.village.save(update_fields=["active"])
        self.assert_followup_permission(False)

    def test_deleted_village_does_not_grant_permission(self):
        self.village.delete()
        self.assert_followup_permission(False)

    def test_officer_and_admin_keep_existing_permission(self):
        self.report.village = self.other_village
        self.report.save(update_fields=["village"])
        for role in (AuthorityUser.Role.OFFICER, AuthorityUser.Role.ADMIN):
            with self.subTest(role=role):
                self.jatujak_reporter.role = role
                self.jatujak_reporter.save(update_fields=["role"])
                self.assert_followup_permission(True)

    def test_superuser_keeps_existing_permission(self):
        self.client.authenticate(self.user)
        self.report.village = None
        self.report.save(update_fields=["village"])
        self.assert_followup_permission(True)

    def test_village_enabled_report_without_village_is_denied(self):
        self.report.village = None
        self.report.save(update_fields=["village"])
        self.assert_followup_permission(False)

    def test_village_disabled_keeps_existing_permission_without_assignments(self):
        set_village_capability_enabled(False)
        self.assignment.delete()
        self.report.village = None
        self.report.save(update_fields=["village"])
        self.assert_followup_permission(True)

    def test_village_disabled_keeps_existing_permission_for_unassigned_village(self):
        set_village_capability_enabled(False)
        self.report.village = self.other_village
        self.report.save(update_fields=["village"])
        self.assert_followup_permission(True)

    def test_village_capability_missing_keeps_existing_permission(self):
        Configuration.objects.get(key=VILLAGE_CAPABILITY_KEY).delete()
        self.assignment.delete()
        self.report.village = None
        self.report.save(update_fields=["village"])
        self.assert_followup_permission(True)

    def test_anonymous_user_cannot_submit_followup(self):
        self.client.logout()
        result = self.client.execute(
            """mutation submit($id: UUID!, $followupId: UUID!, $data: GenericScalar!) {
                submitFollowupReport(
                    incidentId: $id, followupId: $followupId, data: $data
                ) { result { id } }
            }""",
            {
                "id": str(self.report.id),
                "followupId": str(uuid.uuid4()),
                "data": {"condition": "better"},
            },
        )
        self.assertTrue(result.errors)
        self.assertFalse(FollowUpReport.objects.exists())
