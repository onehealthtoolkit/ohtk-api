from django.contrib.gis.geos import Point
from django.utils.timezone import now

from reports.models import IncidentReport
from .base_testcase import BaseTestCase
from ..models import Case


class QueryCasesTestCase(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.mere_case1 = Case.objects.create(
            report=self.mers_report,
            description="mers description1",
            state_definition=self.mers_state_definition,
        )
        self.mers_report2 = IncidentReport.objects.create(
            reported_by=self.user,
            report_type=self.mers_report_type,
            data={"name": "Marry"},
            incident_date=now(),
            relevant_authority_resolved=True,
            gps_location=Point(float(13.30), float(100.25)),
        )
        self.mere_case2 = Case.objects.create(
            report=self.mers_report2,
            description="mers description2",
            state_definition=self.mers_state_definition,
        )
        self.mere_case1.authorities.add(self.bkk)
        self.mere_case2.authorities.add(self.bkk)

    def test_query(self):
        query = """
        query casesQuery {
            casesQuery {
                results {
                    id
                    description
                    report {
                        id
                    }
                    stateDefinition {
                        name
                    }
                    authorities {
                        name
                    }
                }
            }
        }
        """
        result = self.client.execute(query, {})
        self.assertIsNotNone(result.data["casesQuery"])
        self.assertEqual(2, len(result.data["casesQuery"]["results"]))
        self.assertIsNotNone(result.data["casesQuery"]["results"][0]["id"])
        self.assertIsNotNone(result.data["casesQuery"]["results"][0]["authorities"])
        self.assertEqual(
            self.bkk.name,
            result.data["casesQuery"]["results"][0]["authorities"][0]["name"],
        )

    def test_get(self):
        query = """
        query caseGet($id: UUID!) {
            caseGet(id: $id) {                
                id
                description
                report {
                    id
                }
                stateDefinition {
                    name
                }
                authorities {
                    name
                }
            }
        }
        """
        result = self.client.execute(query, {"id": str(self.mere_case1.id)})
        self.assertIsNotNone(result.data["caseGet"])
        self.assertIsNotNone(result.data["caseGet"]["id"])
        self.assertEqual(str(self.mere_case1.id), result.data["caseGet"]["id"])
