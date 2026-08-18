from django.contrib.gis.geos import Point
from django.utils.timezone import now

from cases.models import Case
from cases.tests.base_testcase import BaseTestCase
from reports.models import IncidentReport


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
        self.mers_report2.relevant_authorities.add(self.user.authority)
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
        print(result.data["casesQuery"]["results"])
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

    def test_q_matches_renderer_or_ai_suspected(self):
        # IncidentReport.save() always re-renders renderer_data from the type
        # template, so set the stored text via QuerySet.update.
        IncidentReport.objects.filter(pk=self.mers_report.pk).update(
            renderer_data="Cattle 3 heads"
        )
        IncidentReport.objects.filter(pk=self.mers_report2.pk).update(
            renderer_data="Pig",
            ai_suspected="possible FMD",
        )

        result = self.client.execute(
            """
            query($q: String) {
              casesQuery(q: $q) {
                results { id }
              }
            }
            """,
            {"q": "Cattle"},
        )
        self.assertIsNone(result.errors, result.errors)
        ids = {item["id"] for item in result.data["casesQuery"]["results"]}
        self.assertEqual(ids, {str(self.mere_case1.id)})

        result = self.client.execute(
            """
            query($q: String) {
              casesQuery(q: $q) {
                results { id }
              }
            }
            """,
            {"q": "FMD"},
        )
        self.assertIsNone(result.errors, result.errors)
        ids = {item["id"] for item in result.data["casesQuery"]["results"]}
        self.assertEqual(ids, {str(self.mere_case2.id)})

    def test_case_statuses_filter(self):
        self.mere_case1.is_finished = False
        self.mere_case1.save(update_fields=["is_finished"])
        self.mere_case2.is_finished = True
        self.mere_case2.close_outcome = "false_positive"
        self.mere_case2.close_source = "officer"
        self.mere_case2.save(
            update_fields=["is_finished", "close_outcome", "close_source"]
        )
        closed = Case.objects.create(
            report=self.dengue_report,
            description="closed",
            state_definition=self.mers_state_definition,
            is_finished=True,
            close_outcome="close_case",
            close_source="officer",
        )
        closed.authorities.add(self.bkk)
        auto = Case.objects.create(
            report=self.dengue_report_jatujak,
            description="auto",
            state_definition=self.mers_state_definition,
            is_finished=True,
            close_source="system",
        )
        auto.authorities.add(self.bkk)

        result = self.client.execute(
            """
            query($statuses: String) {
              casesQuery(caseStatuses: $statuses) {
                results { id }
              }
            }
            """,
            {"statuses": "OPEN,FALSE_POSITIVE"},
        )
        self.assertIsNone(result.errors, result.errors)
        ids = {item["id"] for item in result.data["casesQuery"]["results"]}
        self.assertEqual(ids, {str(self.mere_case1.id), str(self.mere_case2.id)})
        self.assertNotIn(str(closed.id), ids)
        self.assertNotIn(str(auto.id), ids)

        result = self.client.execute(
            """
            query($statuses: String) {
              casesQuery(caseStatuses: $statuses) {
                results { id }
              }
            }
            """,
            {"statuses": "AUTOMATIC_CLOSE"},
        )
        self.assertIsNone(result.errors, result.errors)
        ids = {item["id"] for item in result.data["casesQuery"]["results"]}
        self.assertEqual(ids, {str(auto.id)})
