import uuid
from graphql_jwt.testcases import JSONWebTokenTestCase

from cases.models import CaseDefinition
from reports.models.category import Category
from reports.models.report_type import ReportType


class AdminCaseDefinitionTests(JSONWebTokenTestCase):
    def setUp(self):
        self.category = Category.objects.create(name="report category1", ordering=1)
        self.reportType = ReportType.objects.create(
            name="report type1",
            category=self.category,
            definition='{"x":"YYY"}',
            ordering=1,
        )

        self.caseDefinition1 = CaseDefinition.objects.create(
            report_type=self.reportType, description="caseDefinition1", condition="1==1"
        )
        self.caseDefinition2 = CaseDefinition.objects.create(
            report_type=self.reportType, description="caseDefinition2", condition="1==1"
        )

    def test_simple_query(self):
        query = """
        query adminCaseDefinitionQuery {
            adminCaseDefinitionQuery {
                results {
                    id
                    description
                }
            }
        }
        """
        result = self.client.execute(query, {})
        self.assertEqual(len(result.data["adminCaseDefinitionQuery"]["results"]), 2)

    def test_query_with_description(self):
        query = """
        query adminCaseDefinitionQuery($description: String) {
            adminCaseDefinitionQuery(description: $description) {
                results {
                    id
                    description
                }
            }
        }
        """
        result = self.client.execute(query, {"description": "caseDefinition1"})
        self.assertEqual(len(result.data["adminCaseDefinitionQuery"]["results"]), 1)

    def test_create_with_error(self):
        mutation = """
        mutation adminCaseDefinitionCreate($reportTypeId: UUID!, $description: String!, $condition: String!) {
            adminCaseDefinitionCreate(reportTypeId: $reportTypeId, description: $description, condition: $condition) {
                result {
                  __typename
                  ... on AdminCaseDefinitionCreateSuccess {
                    id
                    description
                  }
                  ... on AdminCaseDefinitionCreateProblem {
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
                "reportTypeId": str(uuid.uuid4()),
                "description": "",
                "condition": "",
            },
        )
        self.assertIsNotNone(result.data["adminCaseDefinitionCreate"]["result"])
        self.assertIsNotNone(
            result.data["adminCaseDefinitionCreate"]["result"]["fields"]
        )
        self.assertEqual(
            result.data["adminCaseDefinitionCreate"]["result"]["__typename"],
            "AdminCaseDefinitionCreateProblem",
        )

    def test_create_success(self):
        mutation = """
        mutation adminCaseDefinitionCreate($reportTypeId: UUID!, $description: String!, $condition: String!) {
            adminCaseDefinitionCreate(reportTypeId: $reportTypeId, description: $description, condition: $condition) {
                result {
                  __typename
                  ... on AdminCaseDefinitionCreateSuccess {
                    id
                    description
                  }
                  ... on AdminCaseDefinitionCreateProblem {
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
                "reportTypeId": str(self.reportType.id),
                "description": "description",
                "condition": "yes",
            },
        )
        self.assertIsNotNone(result.data["adminCaseDefinitionCreate"]["result"])
        self.assertIsNotNone(result.data["adminCaseDefinitionCreate"]["result"]["id"])
        self.assertEqual(
            result.data["adminCaseDefinitionCreate"]["result"]["description"],
            "description",
        )

    def test_update_with_error(self):
        mutation = """
        mutation adminCaseDefinitionUpdate($id: ID!, $reportTypeId: UUID!, $description: String!, $condition: String!) {
            adminCaseDefinitionUpdate(id: $id, reportTypeId: $reportTypeId, description: $description, condition: $condition) {
                result {
                  __typename
                  ... on AdminCaseDefinitionUpdateSuccess {
                    caseDefinition {
                      id
                      description
                    }
                  }
                  ... on AdminCaseDefinitionUpdateProblem {
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
                "id": self.caseDefinition1.id,
                "reportTypeId": str(uuid.uuid4()),
                "description": "caseDefinition2",
                "condition": "no",
            },
        )
        print(result)

        self.assertIsNotNone(result.data["adminCaseDefinitionUpdate"]["result"])
        self.assertIsNotNone(
            result.data["adminCaseDefinitionUpdate"]["result"]["fields"]
        )
        self.assertEqual(
            result.data["adminCaseDefinitionUpdate"]["result"]["__typename"],
            "AdminCaseDefinitionUpdateProblem",
        )

    def test_update_success(self):
        mutation = """
        mutation adminCaseDefinitionUpdate($id: ID!, $reportTypeId: UUID!, $description: String!, $condition: String!) {
            adminCaseDefinitionUpdate(id: $id, reportTypeId: $reportTypeId, description: $description, condition: $condition) {
                result {
                  __typename
                  ... on AdminCaseDefinitionUpdateSuccess {
                    caseDefinition {
                      id
                      description
                    }
                  }
                  ... on AdminCaseDefinitionUpdateProblem {
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
                "id": self.caseDefinition1.id,
                "reportTypeId": str(self.reportType.id),
                "description": "caseDefinition2",
                "condition": "no",
            },
        )
        print(result)
        self.assertIsNotNone(result.data["adminCaseDefinitionUpdate"]["result"])
        self.assertIsNotNone(
            result.data["adminCaseDefinitionUpdate"]["result"]["caseDefinition"]["id"]
        )
        self.assertEqual(
            result.data["adminCaseDefinitionUpdate"]["result"]["caseDefinition"][
                "description"
            ],
            "caseDefinition2",
        )
