from graphql_jwt.testcases import JSONWebTokenTestCase

from accounts.models import User
from cases.models import StateDefinition


class AdminStateDefinitionTests(JSONWebTokenTestCase):
    def setUp(self):
        self.stateDefinition1 = StateDefinition.objects.create(
            name="stateDefinition1",
            is_default=True,
        )
        self.stateDefinition2 = StateDefinition.objects.create(
            name="stateDefinition2",
            is_default=False,
        )
        self.user = User.objects.create(username="admintest", is_superuser=True)
        self.client.authenticate(self.user)

    def test_simple_query(self):
        query = """
        query adminStateDefinitionQuery {
            adminStateDefinitionQuery {
                results {
                    id
                    name
                    isDefault
                }
            }
        }
        """
        result = self.client.execute(query, {})
        self.assertEqual(len(result.data["adminStateDefinitionQuery"]["results"]), 2)

    def test_query_with_name(self):
        query = """
        query adminStateDefinitionQuery($name: String) {
            adminStateDefinitionQuery(name: $name) {
                results {
                    id
                    name
                }
            }
        }
        """
        result = self.client.execute(query, {"name": "stateDefinition1"})
        self.assertEqual(len(result.data["adminStateDefinitionQuery"]["results"]), 1)

    def test_create_with_error(self):
        mutation = """
        mutation adminStateDefinitionCreate($name: String!, $isDefault: Boolean!) {
            adminStateDefinitionCreate(name: $name, isDefault: $isDefault) {
                result {
                  __typename
                  ... on AdminStateDefinitionCreateSuccess {
                    id
                    name
                  }
                  ... on AdminStateDefinitionCreateProblem {
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
                "name": "stateDefinition1",
                "isDefault": True,
            },
        )
        self.assertIsNotNone(result.data["adminStateDefinitionCreate"]["result"])
        self.assertIsNotNone(
            result.data["adminStateDefinitionCreate"]["result"]["fields"]
        )
        self.assertEqual(
            result.data["adminStateDefinitionCreate"]["result"]["__typename"],
            "AdminStateDefinitionCreateProblem",
        )

    def test_create_success(self):
        mutation = """
        mutation adminStateDefinitionCreate($name: String!, $isDefault: Boolean!) {
            adminStateDefinitionCreate(name: $name, isDefault: $isDefault) {
                result {
                  __typename
                  ... on AdminStateDefinitionCreateSuccess {
                    id
                    name
                  }
                  ... on AdminStateDefinitionCreateProblem {
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
                "name": "stateDefinition3",
                "isDefault": True,
            },
        )
        self.assertIsNotNone(result.data["adminStateDefinitionCreate"]["result"])
        self.assertIsNotNone(result.data["adminStateDefinitionCreate"]["result"]["id"])
        self.assertEqual(
            result.data["adminStateDefinitionCreate"]["result"]["name"],
            "stateDefinition3",
        )

    def test_update_with_error(self):
        mutation = """
        mutation adminStateDefinitionUpdate($id: ID!, $name: String!, $isDefault: Boolean!) {
            adminStateDefinitionUpdate(id: $id, name: $name, isDefault: $isDefault) {
                result {
                  __typename
                  ... on AdminStateDefinitionUpdateSuccess {
                    stateDefinition {
                      id
                      name
                    }
                  }
                  ... on AdminStateDefinitionUpdateProblem {
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
                "id": self.stateDefinition1.id,
                "name": "stateDefinition2",
                "isDefault": True,
            },
        )

        self.assertIsNotNone(result.data["adminStateDefinitionUpdate"]["result"])
        self.assertIsNotNone(
            result.data["adminStateDefinitionUpdate"]["result"]["fields"]
        )
        self.assertEqual(
            result.data["adminStateDefinitionUpdate"]["result"]["__typename"],
            "AdminStateDefinitionUpdateProblem",
        )

    def test_update_success(self):
        mutation = """
        mutation adminStateDefinitionUpdate($id: ID!, $name: String!, $isDefault: Boolean!) {
            adminStateDefinitionUpdate(id: $id, name: $name, isDefault: $isDefault) {
                result {
                  __typename
                  ... on AdminStateDefinitionUpdateSuccess {
                    stateDefinition {
                      id
                      name
                      isDefault
                    }
                  }
                  ... on AdminStateDefinitionUpdateProblem {
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
                "id": self.stateDefinition1.id,
                "name": "stateDefinition3",
                "isDefault": True,
            },
        )
        self.assertIsNotNone(result.data["adminStateDefinitionUpdate"]["result"])
        self.assertIsNotNone(
            result.data["adminStateDefinitionUpdate"]["result"]["stateDefinition"]["id"]
        )
        self.assertEqual(
            result.data["adminStateDefinitionUpdate"]["result"]["stateDefinition"][
                "name"
            ],
            "stateDefinition3",
        )
