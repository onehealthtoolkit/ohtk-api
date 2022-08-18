from graphql_jwt.testcases import JSONWebTokenTestCase

from accounts.models import User
from reports.models.category import Category

from reports.models.report_type import ReportType


class AdminReportTypeTests(JSONWebTokenTestCase):
    def setUp(self):
        self.category = Category.objects.create(name="report type1", ordering=1)
        self.reportType1 = ReportType.objects.create(
            name="report type1",
            category=self.category,
            definition='{"x":"YYY"}',
            ordering=1,
        )
        self.reportType2 = ReportType.objects.create(
            name="report type2",
            category=self.category,
            definition='{"y":"XXX"}',
            ordering=2,
        )
        self.user = User.objects.create(username="admintest", is_superuser=True)
        self.client.authenticate(self.user)

    def test_simple_query(self):
        query = """
        query adminReportTypeQuery {
            adminReportTypeQuery {
                results {
                    id
                    name
                    ordering

                }
            }
        }
        """
        result = self.client.execute(query, {})
        self.assertEqual(len(result.data["adminReportTypeQuery"]["results"]), 2)

    def test_query_with_name(self):
        query = """
        query adminReportTypeQuery($q: String) {
            adminReportTypeQuery(q: $q) {
                results {
                    id
                    name
                    ordering
                }
            }
        }
        """
        result = self.client.execute(query, {"q": "report type1"})
        self.assertEqual(len(result.data["adminReportTypeQuery"]["results"]), 2)

    def test_create_with_error(self):
        mutation = """
        mutation adminReportTypeCreate($name: String!, $definition: String!, $ordering: Int!) {
            adminReportTypeCreate(name: $name, definition: $definition, ordering: $ordering) {
                result {
                  __typename
                  ... on AdminReportTypeCreateSuccess {
                    id
                    name
                    ordering
                  }
                  ... on AdminReportTypeCreateProblem {
                    message
                    fields {
                      name
                      message
                    }
                  }
                }
            }
        }
        """
        result = self.client.execute(
            mutation,
            {
                "name": "report type1",
                "definition": '{"x":"YYYYY"}',
                "ordering": 1,
            },
        )
        self.assertIsNotNone(result.data["adminReportTypeCreate"]["result"])
        self.assertIsNotNone(result.data["adminReportTypeCreate"]["result"]["fields"])
        self.assertEqual(
            result.data["adminReportTypeCreate"]["result"]["fields"][0]["name"],
            "name",
        )

    def test_create_success(self):
        mutation = """
        mutation adminReportTypeCreate($name: String!, $categoryId: Int!, $definition: String!, $ordering: Int!) {
            adminReportTypeCreate(name: $name, definition: $definition, categoryId: $categoryId, ordering: $ordering) {
                result {
                  __typename
                  ... on AdminReportTypeCreateSuccess {
                    id
                    name
                    ordering
                  }
                  ... on AdminReportTypeCreateProblem {
                    message
                    fields {
                      name
                      message
                    }
                  }
                }
            }
        }
        """
        result = self.client.execute(
            mutation,
            {
                "name": "cat3",
                "categoryId": self.category.id,
                "definition": '{"x":"YYYYY"}',
                "ordering": 3,
            },
        )
        self.assertIsNotNone(result.data["adminReportTypeCreate"]["result"])
        self.assertIsNotNone(result.data["adminReportTypeCreate"]["result"]["id"])
        self.assertEqual(result.data["adminReportTypeCreate"]["result"]["name"], "cat3")

    def test_update_with_error(self):
        mutation = """
        mutation adminReportTypeUpdate($id: ID!, $name: String!, $ordering: Int!) {
            adminReportTypeUpdate(id: $id, name: $name, ordering: $ordering) {
                result {
                  __typename
                  ... on AdminReportTypeUpdateSuccess {
                    reportType {
                        id
                        name
                        ordering
                    }
                  }
                  ... on AdminReportTypeUpdateProblem {
                    message
                    fields {
                      name
                      message
                    }
                  }
                }
            }
        }
        
        """
        result = self.client.execute(
            mutation,
            {
                "id": str(self.reportType1.id),
                "name": "report type2",
                "ordering": 1,
            },
        )
        self.assertIsNotNone(result.data["adminReportTypeUpdate"]["result"])
        self.assertIsNotNone(result.data["adminReportTypeUpdate"]["result"]["fields"])
        self.assertEqual(
            result.data["adminReportTypeUpdate"]["result"]["fields"][0]["name"],
            "name",
        )

    def test_update_success(self):
        mutation = """
        mutation adminReportTypeUpdate($id: ID!, $name: String!, $categoryId: Int!, $definition: String!, $ordering: Int!) {
            adminReportTypeUpdate(id: $id, name: $name, definition: $definition, categoryId: $categoryId, ordering: $ordering) {
                result {
                  __typename
                  ... on AdminReportTypeUpdateSuccess {
                    reportType {
                        id
                        name
                        ordering
                    }
                  }
                  ... on AdminReportTypeUpdateProblem {
                    message
                    fields {
                      name
                      message
                    }
                  }
                }
            }
        }
        """
        result = self.client.execute(
            mutation,
            {
                "id": str(self.reportType1.id),
                "name": "report type 3",
                "categoryId": self.category.id,
                "definition": '{"z":"AAAAAA"}',
                "ordering": 5,
            },
        )

        self.assertIsNotNone(result.data["adminReportTypeUpdate"]["result"])
        self.assertIsNotNone(
            result.data["adminReportTypeUpdate"]["result"]["reportType"]["id"]
        )
        self.assertEqual(
            result.data["adminReportTypeUpdate"]["result"]["reportType"]["name"],
            "report type 3",
        )
