import uuid

from django.utils.timezone import now
from graphql_jwt.testcases import JSONWebTokenClient

from reports.models import IncidentReport
from reports.tests.base_testcase import BaseTestCase


class FollowupTestCase(BaseTestCase):
    client_class = JSONWebTokenClient

    def setUp(self):
        super().setUp()
        self.client.authenticate(self.user)
        self.report = IncidentReport.objects.create(
            data={
                "symptom": "cough",
                "number_of_sick": 1,
            },
            reported_by=self.user,
            incident_date=now(),
            report_type=self.mers_report_type,
        )

    def test_submit_followup(self):
        mutation = """
                    mutation submit($data: GenericScalar!, $incidentId: UUID!, $followupId: UUID) {
                        submitFollowupReport(data: $data,
                                             incidentId: $incidentId,
                                             followupId: $followupId) {                                     
                            result {
                                id                                                        
                            }                                
                        }
                    }
                """
        followup_id = uuid.uuid4()
        result = self.client.execute(
            mutation,
            {
                "data": {
                    "symptom": "cough",
                    "number_of_sick": 1,
                },
                "followupId": str(followup_id),
                "incidentId": str(self.report.id),
            },
        )
        self.assertIsNone(result.errors, msg=result.errors)
        result_data = result.data["submitFollowupReport"]["result"]
        self.assertEqual(str(followup_id), str(result_data["id"]))
