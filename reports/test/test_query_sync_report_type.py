import uuid

from django.contrib.auth import get_user_model

from graphql_jwt.testcases import JSONWebTokenTestCase

from accounts.models import AuthorityUser, Authority
from reports.models import Category, ReportType

query = """
        query sync($data: [ReportTypeSyncInputType!]!) {
          syncReportTypes(data: $data) {
            updatedList {
              id
            } 
            removedList {
              id
            }
          }
        }

        """


class QuerySyncReportTestCase(JSONWebTokenTestCase):
    def setUp(self):

        self.thailand = Authority.objects.create(code="TH", name="Thailand")
        self.human_category = Category.objects.create(name="human")
        self.dengue_report_type = ReportType.objects.create(
            name="Dengue",
            category=self.human_category,
            definition={},
        )
        self.dengue_report_type.authorities.add(self.thailand)
        self.mers_report_type = ReportType.objects.create(
            name="Mers",
            category=self.human_category,
            definition={},
        )
        self.mers_report_type.authorities.add(self.thailand)
        self.snapshot = list(map(lambda item: item.to_data(), ReportType.objects.all()))

        self.query_params = {
            "data": list(
                map(
                    lambda item: {
                        "id": item.id.hex,
                        "updatedAt": item.updated_at,
                    },
                    self.snapshot,
                )
            )
        }

        self.user = AuthorityUser.objects.create(
            username="test", authority=self.thailand
        )
        self.client.authenticate(self.user)

    def test_sync_report_for_first_time(self):
        result = self.client.execute(query, {"data": []})

        self.assertEqual(2, len(result.data["syncReportTypes"]["updatedList"]))
        self.assertEqual(0, len(result.data["syncReportTypes"]["removedList"]))

    def test_sync_report_for_no_changed(self):
        result = self.client.execute(query, self.query_params)
        self.assertIsNone(result.errors)

        self.assertEqual(0, len(result.data["syncReportTypes"]["updatedList"]))
        self.assertEqual(0, len(result.data["syncReportTypes"]["removedList"]))

    def test_sync_report_with_changed(self):
        self.mers_report_type.definition = {"changeme": True}
        self.mers_report_type.save()
        result = self.client.execute(query, self.query_params)
        self.assertIsNone(result.errors)

        self.assertEqual(1, len(result.data["syncReportTypes"]["updatedList"]))
        self.assertEqual(0, len(result.data["syncReportTypes"]["removedList"]))

    def test_sync_report_with_some_type_was_removed(self):
        self.mers_report_type.authorities.clear()
        result = self.client.execute(query, self.query_params)
        self.assertIsNone(result.errors)

        self.assertEqual(0, len(result.data["syncReportTypes"]["updatedList"]))
        self.assertEqual(1, len(result.data["syncReportTypes"]["removedList"]))
