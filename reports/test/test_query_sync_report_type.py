from graphql_jwt.testcases import JSONWebTokenClient

from reports.test.base_testcase import BaseTestCase

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


class QuerySyncReportTestCase(BaseTestCase):
    client_class = JSONWebTokenClient

    def setUp(self):
        super(QuerySyncReportTestCase, self).setUp()
        self.query_params = {
            "data": list(
                map(
                    lambda item: {
                        "id": item.id.hex,
                        "updatedAt": item.updated_at,
                    },
                    self.thailand_reports,
                )
            )
        }

        self.client.authenticate(self.user)

    def test_sync_report_for_first_time(self):
        result = self.client.execute(query, {"data": []})

        self.assertEqual(3, len(result.data["syncReportTypes"]["updatedList"]))
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
