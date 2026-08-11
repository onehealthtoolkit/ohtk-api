import uuid

from django.contrib.gis.geos import Point
from graphql_jwt.testcases import JSONWebTokenClient

from accounts.models import Village, VillageReporterAssignment
from accounts.report_location_fallback import (
    FEATURE_DISABLED_VALUE,
    FEATURE_ENABLED_VALUE,
    REPORT_USE_VILLAGE_LOCATION_FALLBACK_KEY,
    set_report_use_village_location_fallback_enabled,
)
from accounts.models import Configuration
from reports.models import IncidentReport
from reports.tests.base_testcase import BaseTestCase


class ReportVillageLocationFallbackTestCase(BaseTestCase):
    client_class = JSONWebTokenClient

    def setUp(self):
        super().setUp()
        self.client.authenticate(self.jatujak_reporter)
        self.village = Village.objects.create(
            authority=self.jatujak,
            code="V-JT",
            name="Jatujak Village",
            location=Point(100.55, 13.80),
            active=True,
        )
        VillageReporterAssignment.objects.create(
            reporter=self.jatujak_reporter,
            village=self.village,
            census_role=VillageReporterAssignment.CensusRole.OFFICIAL,
        )

    def _submit(
        self, report_id=None, gps_location=None, village_id=None, expect_errors=False
    ):
        mutation = """
            mutation submit(
                $data: GenericScalar!,
                $reportTypeId: UUID!,
                $incidentDate: Date!,
                $reportId: UUID,
                $gpsLocation: String,
                $villageId: Int
            ) {
                submitIncidentReport(
                    data: $data,
                    reportTypeId: $reportTypeId,
                    incidentDate: $incidentDate,
                    reportId: $reportId,
                    gpsLocation: $gpsLocation,
                    villageId: $villageId
                ) {
                    result {
                        id
                        gpsLocation
                        village {
                            id
                        }
                    }
                }
            }
        """
        variables = {
            "data": {"symptom": "cough", "number_of_sick": 1},
            "reportTypeId": str(self.mers_report_type.id),
            "incidentDate": "2022-03-18",
            "reportId": str(report_id or uuid.uuid4()),
        }
        if gps_location is not None:
            variables["gpsLocation"] = gps_location
        if village_id is not None:
            variables["villageId"] = village_id
        result = self.client.execute(mutation, variables)
        if expect_errors:
            return result
        self.assertIsNone(result.errors, msg=result.errors)
        return result.data["submitIncidentReport"]["result"]

    def _assert_no_gps(self, data):
        # GraphQL may return null or empty string for missing PointField
        self.assertFalse(data.get("gpsLocation"))
        report = IncidentReport.objects.get(id=data["id"])
        self.assertIsNone(report.gps_location)

    def test_config_disabled_no_client_gps_leaves_null(self):
        set_report_use_village_location_fallback_enabled(False)
        data = self._submit()
        self._assert_no_gps(data)

    def test_config_missing_no_client_gps_leaves_null(self):
        Configuration.objects.filter(
            key=REPORT_USE_VILLAGE_LOCATION_FALLBACK_KEY
        ).delete()
        data = self._submit()
        self._assert_no_gps(data)

    def test_config_enabled_no_client_gps_uses_village(self):
        set_report_use_village_location_fallback_enabled(True)
        data = self._submit()
        report = IncidentReport.objects.get(id=data["id"])
        self.assertIsNotNone(report.gps_location)
        self.assertAlmostEqual(report.gps_location.x, 100.55)
        self.assertAlmostEqual(report.gps_location.y, 13.80)
        self.assertTrue(data["gpsLocation"])

    def test_config_enabled_client_gps_wins_over_village(self):
        set_report_use_village_location_fallback_enabled(True)
        client_gps = "101.00300,13.23300"
        data = self._submit(
            gps_location=client_gps,
            village_id=self.village.id,
        )
        self.assertEqual(data["gpsLocation"], client_gps)

    def test_reporter_can_submit_an_assigned_village(self):
        set_report_use_village_location_fallback_enabled(False)

        data = self._submit(village_id=self.village.id)

        report = IncidentReport.objects.get(id=data["id"])
        self.assertEqual(report.village, self.village)
        self.assertEqual(data["village"]["id"], self.village.id)
        self.assertAlmostEqual(report.gps_location.x, self.village.location.x)
        self.assertAlmostEqual(report.gps_location.y, self.village.location.y)

    def test_reporter_cannot_submit_an_unassigned_village(self):
        other = Village.objects.create(
            authority=self.jatujak,
            code="V-JT2",
            name="Other Village",
            location=Point(100.99, 13.99),
            active=True,
        )

        result = self._submit(village_id=other.id, expect_errors=True)

        self.assertIsNotNone(result.errors)
        self.assertIn("village is not assigned to reporter", str(result.errors))

    def test_selected_village_location_wins_over_assignment_fallback(self):
        set_report_use_village_location_fallback_enabled(True)
        selected = Village.objects.create(
            authority=self.jatujak,
            code="V-JT2",
            name="Selected Village",
            location=Point(100.99, 13.99),
            active=True,
        )
        VillageReporterAssignment.objects.create(
            reporter=self.jatujak_reporter,
            village=selected,
            census_role=VillageReporterAssignment.CensusRole.OFFICIAL,
        )

        data = self._submit(village_id=selected.id)

        report = IncidentReport.objects.get(id=data["id"])
        self.assertEqual(report.village, selected)
        self.assertAlmostEqual(report.gps_location.x, selected.location.x)
        self.assertAlmostEqual(report.gps_location.y, selected.location.y)

    def test_config_enabled_village_without_location_null(self):
        set_report_use_village_location_fallback_enabled(True)
        self.village.location = None
        self.village.save(update_fields=["location"])
        data = self._submit()
        self._assert_no_gps(data)

    def test_config_enabled_no_assignment_null(self):
        set_report_use_village_location_fallback_enabled(True)
        VillageReporterAssignment.objects.filter(
            reporter=self.jatujak_reporter
        ).delete()
        data = self._submit()
        self._assert_no_gps(data)

    def test_multi_village_uses_lowest_village_id(self):
        set_report_use_village_location_fallback_enabled(True)
        other = Village.objects.create(
            authority=self.jatujak,
            code="V-JT2",
            name="Other Village",
            location=Point(100.99, 13.99),
            active=True,
        )
        VillageReporterAssignment.objects.create(
            reporter=self.jatujak_reporter,
            village=other,
            census_role=VillageReporterAssignment.CensusRole.OFFICIAL,
        )
        expected = self.village if self.village.id < other.id else other
        data = self._submit()
        report = IncidentReport.objects.get(id=data["id"])
        self.assertAlmostEqual(report.gps_location.x, expected.location.x)
        self.assertAlmostEqual(report.gps_location.y, expected.location.y)

    def test_admin_mutation_superuser_only(self):
        query = """
        mutation adminReportUseVillageLocationFallbackUpdate($enabled: Boolean!) {
            adminReportUseVillageLocationFallbackUpdate(enabled: $enabled) {
                enabled
            }
        }
        """
        # reporter is not superuser
        result = self.client.execute(query, {"enabled": True})
        self.assertIsNotNone(result.errors)

        self.client.authenticate(self.user)  # superuser AuthorityUser
        result = self.client.execute(query, {"enabled": True})
        self.assertIsNone(result.errors, msg=result.errors)
        self.assertTrue(
            result.data["adminReportUseVillageLocationFallbackUpdate"]["enabled"]
        )
        self.assertTrue(
            Configuration.objects.filter(
                key=REPORT_USE_VILLAGE_LOCATION_FALLBACK_KEY,
                value=FEATURE_ENABLED_VALUE,
            ).exists()
        )

        result = self.client.execute(query, {"enabled": False})
        self.assertIsNone(result.errors, msg=result.errors)
        self.assertTrue(
            Configuration.objects.filter(
                key=REPORT_USE_VILLAGE_LOCATION_FALLBACK_KEY,
                value=FEATURE_DISABLED_VALUE,
            ).exists()
        )
