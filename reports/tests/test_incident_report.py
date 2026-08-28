import uuid

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.utils.timezone import now
from graphql_jwt.testcases import JSONWebTokenClient

from accounts.models import Village, VillageReporterAssignment
from accounts.report_restrict_to_assigned_scope import (
    set_report_restrict_to_assigned_scope_enabled,
)
from reports.models import IncidentReport
from reports.tests.base_testcase import BaseTestCase


class IncidentReportTestCase(BaseTestCase):
    client_class = JSONWebTokenClient

    def setUp(self):
        super().setUp()
        self.client.authenticate(self.user)

    def test_create_report(self):
        self.mers_report_type.renderer_data_template = (
            """found {{ data.number_of_sick }} with symptom: {{ data.symptom }}"""
        )
        self.mers_report_type.save()

        report = IncidentReport.objects.create(
            data={
                "symptom": "cough",
                "number_of_sick": 1,
            },
            reported_by=self.user,
            incident_date=now(),
            report_type=self.mers_report_type,
        )
        self.assertIsNotNone(report.id)
        self.assertEqual("found 1 with symptom: cough", report.renderer_data)

    def test_create_report_with_passing_uuid_from_client(self):
        passing_uuid = uuid.uuid4()
        report = IncidentReport.objects.create(
            id=passing_uuid,
            data={
                "symptom": "cough",
                "number_of_sick": 1,
            },
            reported_by=self.user,
            incident_date=now(),
            report_type=self.mers_report_type,
        )
        self.assertEqual(passing_uuid, report.id)

    def test_mutation_create_report(self):
        self.client.authenticate(self.user)
        mutation = """
            mutation submit($data: GenericScalar!, $reportTypeId: UUID!, $incidentDate: Date!, $reportId: UUID) {
                submitIncidentReport(data: $data,
                                     reportTypeId: $reportTypeId,
                                     incidentDate: $incidentDate,
                                     reportId: $reportId) {                                     
                    result {
                        id
                        rendererData                        
                    }                                
                }
            }
        """
        report_id = uuid.uuid4()
        result = self.client.execute(
            mutation,
            {
                "data": {
                    "symptom": "cough",
                    "number_of_sick": 1,
                },
                "reportTypeId": str(self.mers_report_type.id),
                "reportId": str(report_id),
                "incidentDate": "2022-03-18",
            },
        )
        self.assertIsNone(result.errors, msg=result.errors)
        result_data = result.data["submitIncidentReport"]["result"]
        self.assertEqual(str(report_id), str(result_data["id"]))
        self.assertEqual(
            "number of sick 1 with symptom cough", result_data["rendererData"]
        )

    def test_submit_gps_location(self):
        mutation = """
                    mutation submit($data: GenericScalar!, $reportTypeId: UUID!, $incidentDate: Date!, $reportId: UUID, $gpsLocation: String) {
                        submitIncidentReport(data: $data,
                                             reportTypeId: $reportTypeId,
                                             incidentDate: $incidentDate,
                                             reportId: $reportId,
                                             gpsLocation: $gpsLocation) {                                     
                            result {
                                id
                                rendererData                        
                                gpsLocation
                            }                                
                        }
                    }
                """
        report_id = uuid.uuid4()
        LOCATION = "101.00300,13.23300"  # longitude, latitude
        result = self.client.execute(
            mutation,
            {
                "data": {
                    "symptom": "cough",
                    "number_of_sick": 1,
                },
                "reportTypeId": str(self.mers_report_type.id),
                "reportId": str(report_id),
                "incidentDate": "2022-03-18",
                "gpsLocation": LOCATION,
            },
        )
        self.assertIsNone(result.errors, msg=result.errors)
        result_data = result.data["submitIncidentReport"]["result"]
        self.assertEqual(LOCATION, result_data["gpsLocation"])

    def test_submit_within_own_authority(self):
        mutation = """
                            mutation submit($data: GenericScalar!, $reportTypeId: UUID!, $incidentDate: Date!, $reportId: UUID, $gpsLocation: String, $incidentInAuthority: Boolean) {
                                submitIncidentReport(data: $data,
                                                     reportTypeId: $reportTypeId,
                                                     incidentDate: $incidentDate,
                                                     reportId: $reportId,
                                                     gpsLocation: $gpsLocation,
                                                     incidentInAuthority: $incidentInAuthority) {                                     
                                    result {
                                        id
                                        rendererData                        
                                        relevantAuthorityResolved
                                        relevantAuthorities {
                                            id
                                        }
                                    }                                
                                }
                            }
                        """
        report_id = uuid.uuid4()
        result = self.client.execute(
            mutation,
            {
                "data": {
                    "symptom": "cough",
                    "number_of_sick": 1,
                },
                "reportTypeId": str(self.mers_report_type.id),
                "reportId": str(report_id),
                "incidentDate": "2022-03-18",
                "incidentInAuthority": True,
            },
        )
        self.assertIsNone(result.errors, msg=result.errors)
        result_data = result.data["submitIncidentReport"]["result"]
        self.assertEqual(True, result_data["relevantAuthorityResolved"])
        self.assertEqual(
            str(self.user.authority.id), result_data["relevantAuthorities"][0]["id"]
        )

    def test_submit_outside_their_own_authority_but_resolve_by_area(self):
        mutation = """
                            mutation submit($data: GenericScalar!, $reportTypeId: UUID!, $incidentDate: Date!, $reportId: UUID, $gpsLocation: String, $incidentInAuthority: Boolean) {
                                submitIncidentReport(data: $data,
                                                     reportTypeId: $reportTypeId,
                                                     incidentDate: $incidentDate,
                                                     reportId: $reportId,
                                                     gpsLocation: $gpsLocation,
                                                     incidentInAuthority: $incidentInAuthority) {                                     
                                    result {
                                        id
                                        rendererData                        
                                        relevantAuthorityResolved
                                        relevantAuthorities {
                                            id
                                        }
                                    }                                
                                }
                            }
                        """
        report_id = uuid.uuid4()
        result = self.client.execute(
            mutation,
            {
                "data": {
                    "symptom": "cough",
                    "number_of_sick": 1,
                },
                "reportTypeId": str(self.mers_report_type.id),
                "reportId": str(report_id),
                "incidentDate": "2022-03-18",
                "incidentInAuthority": False,
                "gpsLocation": "100.5523681640625,13.856747234606724",
            },
        )
        self.assertIsNone(result.errors, msg=result.errors)
        result_data = result.data["submitIncidentReport"]["result"]
        self.assertEqual(True, result_data["relevantAuthorityResolved"])
        authorities = result_data["relevantAuthorities"]
        self.assertEqual(1, len(authorities))
        self.assertEqual(
            str(self.bkk.id), authorities[0]["id"]
        )  # "pk" field in graphene is str type

    def test_restrict_to_assigned_scope_ignores_outside_authority_gps(self):
        set_report_restrict_to_assigned_scope_enabled(True)
        mutation = """
            mutation submit($data: GenericScalar!, $reportTypeId: UUID!, $incidentDate: Date!, $reportId: UUID, $gpsLocation: String, $incidentInAuthority: Boolean) {
                submitIncidentReport(data: $data,
                                     reportTypeId: $reportTypeId,
                                     incidentDate: $incidentDate,
                                     reportId: $reportId,
                                     gpsLocation: $gpsLocation,
                                     incidentInAuthority: $incidentInAuthority) {
                    result {
                        id
                        relevantAuthorityResolved
                        relevantAuthorities {
                            id
                        }
                    }
                }
            }
        """
        result = self.client.execute(
            mutation,
            {
                "data": {"symptom": "cough", "number_of_sick": 1},
                "reportTypeId": str(self.mers_report_type.id),
                "reportId": str(uuid.uuid4()),
                "incidentDate": "2022-03-18",
                "incidentInAuthority": False,
                "gpsLocation": "100.5523681640625,13.856747234606724",
            },
        )
        self.assertIsNone(result.errors, msg=result.errors)
        result_data = result.data["submitIncidentReport"]["result"]
        self.assertTrue(result_data["relevantAuthorityResolved"])
        authorities = result_data["relevantAuthorities"]
        self.assertEqual(1, len(authorities))
        self.assertEqual(str(self.user.authority.id), authorities[0]["id"])

    def test_restrict_to_assigned_scope_uses_village_authority(self):
        set_report_restrict_to_assigned_scope_enabled(True)
        village = Village.objects.create(
            authority=self.jatujak,
            code="V-JT",
            name="Jatujak Village",
            location=Point(100.55, 13.80),
            active=True,
        )
        VillageReporterAssignment.objects.create(
            reporter=self.jatujak_reporter,
            village=village,
            census_role=VillageReporterAssignment.CensusRole.OFFICIAL,
        )
        self.client.authenticate(self.jatujak_reporter)
        mutation = """
            mutation submit($data: GenericScalar!, $reportTypeId: UUID!, $incidentDate: Date!, $reportId: UUID, $gpsLocation: String, $incidentInAuthority: Boolean, $villageId: Int) {
                submitIncidentReport(data: $data,
                                     reportTypeId: $reportTypeId,
                                     incidentDate: $incidentDate,
                                     reportId: $reportId,
                                     gpsLocation: $gpsLocation,
                                     incidentInAuthority: $incidentInAuthority,
                                     villageId: $villageId) {
                    result {
                        id
                        relevantAuthorityResolved
                        relevantAuthorities {
                            id
                        }
                        village {
                            id
                        }
                    }
                }
            }
        """
        result = self.client.execute(
            mutation,
            {
                "data": {"symptom": "cough", "number_of_sick": 1},
                "reportTypeId": str(self.mers_report_type.id),
                "reportId": str(uuid.uuid4()),
                "incidentDate": "2022-03-18",
                "incidentInAuthority": False,
                "gpsLocation": "100.5523681640625,13.856747234606724",
                "villageId": village.id,
            },
        )
        self.assertIsNone(result.errors, msg=result.errors)
        result_data = result.data["submitIncidentReport"]["result"]
        self.assertTrue(result_data["relevantAuthorityResolved"])
        self.assertEqual(str(village.id), str(result_data["village"]["id"]))
        authorities = result_data["relevantAuthorities"]
        self.assertEqual(1, len(authorities))
        self.assertEqual(str(self.jatujak.id), authorities[0]["id"])

    def test_query_report_data_summary(self):
        self.client.authenticate(self.user)
        query = """
            query reportDataSummary($data: GenericScalar!, $reportTypeId: UUID!, $incidentDate: Date!) {
                reportDataSummary(data: $data, reportTypeId: $reportTypeId, incidentDate: $incidentDate) {
                    result
                }
            }
        """
        result = self.client.execute(
            query,
            {
                "data": {
                    "symptom": "cough",
                    "number_of_sick": 1,
                },
                "reportTypeId": str(self.mers_report_type.id),
                "incidentDate": "2022-03-18",
            },
        )
        self.assertIsNone(result.errors, msg=result.errors)
        result_data = result.data["reportDataSummary"]["result"]
        self.assertEqual("number of sick 1 with symptom cough", result_data)

    def test_query_followup_report_data_summary(self):
        self.client.authenticate(self.user)
        query = """
            query followupReportDataSummary($data: GenericScalar!, $reportTypeId: UUID!, $incidentReportId: UUID!) {
                followupReportDataSummary(data: $data, reportTypeId: $reportTypeId, incidentReportId: $incidentReportId) {
                    result
                }
            }
        """
        report = IncidentReport.objects.create(
            data={
                "symptom": "cough",
                "number_of_sick": 1,
            },
            reported_by=self.user,
            incident_date=now(),
            report_type=self.mers_report_type,
        )
        result = self.client.execute(
            query,
            {
                "incidentReportId": str(report.id),
                "data": {
                    "condition": "light",
                    "number_of_days": 2,
                },
                "reportTypeId": str(self.mers_report_type.id),
            },
        )
        self.assertIsNone(result.errors, msg=result.errors)
        result_data = result.data["followupReportDataSummary"]["result"]
        self.assertEqual(
            "symptom cough last for 2 days with light condition", result_data
        )
