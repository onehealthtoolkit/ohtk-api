import uuid

from django.contrib.auth import get_user_model
from django.utils.timezone import now
from graphql_jwt.testcases import JSONWebTokenClient

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
        LOCATION = "13.233,101.003"
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

    def test_submit_outside_their_own_authority(self):
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
            },
        )
        self.assertIsNone(result.errors, msg=result.errors)
        result_data = result.data["submitIncidentReport"]["result"]
        self.assertEqual(False, result_data["relevantAuthorityResolved"])
        self.assertEqual(0, len(result_data["relevantAuthorities"]))
