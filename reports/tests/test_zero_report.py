from graphql_jwt.testcases import JSONWebTokenClient

from reports.models import ZeroReport
from reports.tests.base_testcase import BaseTestCase

query = """
    mutation submitZeroReport {
        submitZeroReport {
            id
        }
    }
"""


class ZeroReportTestCase(BaseTestCase):
    client_class = JSONWebTokenClient

    def setUp(self):
        super(ZeroReportTestCase, self).setUp()
        self.client.authenticate(self.user)

    def test_create_zero_report(self):
        result = self.client.execute(query)
        self.assertIsNotNone(result.data["submitZeroReport"]["id"])
        report_id = result.data["submitZeroReport"]["id"]
        instance = ZeroReport.objects.get(pk=report_id)
        self.assertIsNotNone(instance)
        self.assertIsNotNone(instance.created_at)
        self.assertEqual(instance.reported_by.id, self.user.id)
