from graphql_jwt.testcases import JSONWebTokenTestCase

from accounts.models import User
from observations.models import Definition


class AdminObservationDefinitionTests(JSONWebTokenTestCase):
    def setUp(self):
        self.definition1 = Definition.objects.create(
            name="definition1",
            description="description1",
            is_active=True,
            register_form_definition="{}",
            title_template="title",
            description_template="template",
            identity_template="identity template",
        )
        self.definition2 = Definition.objects.create(
            name="definition2",
            description="description 2",
            is_active=True,
            register_form_definition="{}",
            title_template="title2",
            description_template="template 2",
            identity_template="identity template 2",
        )
        self.user = User.objects.create(username="admintest", is_superuser=True)
        self.client.authenticate(self.user)

    def test_simple_query(self):
        query = """
        query adminObservationDefinitionQuery {
            adminObservationDefinitionQuery {
                results {
                    id
                    name
                    description
                }
            }
        }
        """
        result = self.client.execute(query, {})
        self.assertEqual(
            len(result.data["adminObservationDefinitionQuery"]["results"]), 2
        )

    def test_query_with_name(self):
        query = """
        query adminObservationDefinitionQuery($name: String) {
            adminObservationDefinitionQuery(q: $name) {
                results {
                    id
                    name
                    description
                }
            }
        }
        """
        result = self.client.execute(query, {"name": "definition1"})
        self.assertEqual(
            len(result.data["adminObservationDefinitionQuery"]["results"]), 1
        )

    def test_create_with_error(self):
        mutation = """
        mutation adminObservationDefinitionCreate($name: String, $description: String!, $titleTemplate: String!, $descriptionTemplate: String!, $identityTemplate: String!, $registerFormDefinition: JSONString!) {
            adminObservationDefinitionCreate(name: $name, description: $description, titleTemplate: $titleTemplate, descriptionTemplate: $descriptionTemplate, identityTemplate: $identityTemplate, registerFormDefinition: $registerFormDefinition) {
                result {
                  __typename
                  ... on AdminObservationDefinitionCreateSuccess {
                    name
                    id
                    createdAt
                  }
                  ... on AdminObservationDefinitionCreateProblem {
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
                "name": "definition1",
                "description": "description one",
                "titleTemplate": "titleTemplate",
                "descriptionTemplate": "descriptionTemplate",
                "identityTemplate": "identityTemplate",
                "registerFormDefinition": "{}",
            },
        )
        self.assertIsNotNone(result.data["adminObservationDefinitionCreate"]["result"])
        self.assertIsNotNone(
            result.data["adminObservationDefinitionCreate"]["result"]["fields"]
        )
        self.assertEqual(
            result.data["adminObservationDefinitionCreate"]["result"]["fields"][0][
                "name"
            ],
            "name",
        )

    def test_create_success(self):
        mutation = """
        mutation adminObservationDefinitionCreate($name: String!, $description: String!, $titleTemplate: String!, $descriptionTemplate: String!, $identityTemplate: String!, $registerFormDefinition: JSONString!) {
            adminObservationDefinitionCreate(name: $name, description: $description, titleTemplate: $titleTemplate, descriptionTemplate: $descriptionTemplate, identityTemplate: $identityTemplate, registerFormDefinition: $registerFormDefinition) {
                result {
                  __typename
                  ... on AdminObservationDefinitionCreateSuccess {
                    name
                    id
                    createdAt
                  }
                  ... on AdminObservationDefinitionCreateProblem {
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
                "name": "definition3",
                "description": "description one",
                "titleTemplate": "titleTemplate",
                "descriptionTemplate": "descriptionTemplate",
                "identityTemplate": "identityTemplate",
                "registerFormDefinition": "{}",
            },
        )
        self.assertIsNotNone(result.data["adminObservationDefinitionCreate"]["result"])
        self.assertIsNotNone(
            result.data["adminObservationDefinitionCreate"]["result"]["id"]
        )
        self.assertEqual(
            result.data["adminObservationDefinitionCreate"]["result"]["name"],
            "definition3",
        )

    def test_update_with_error(self):
        mutation = """
        mutation adminObservationDefinitionUpdate($id: ID!, $name: String!, $description: String!, $titleTemplate: String!, $descriptionTemplate: String!, $identityTemplate: String!, $registerFormDefinition: JSONString!) {
            adminObservationDefinitionUpdate(id: $id, name: $name, description: $description, titleTemplate: $titleTemplate, descriptionTemplate: $descriptionTemplate, identityTemplate: $identityTemplate, registerFormDefinition: $registerFormDefinition) {
                result {
                  __typename
                  ... on AdminObservationDefinitionUpdateSuccess {
                    definition {
                        name
                        id
                        name
                    }
                  }
                  ... on AdminObservationDefinitionUpdateProblem {
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
                "id": self.definition1.id,
                "name": "definition2",
                "description": "description one",
                "titleTemplate": "titleTemplate",
                "descriptionTemplate": "descriptionTemplate",
                "identityTemplate": "identityTemplate",
                "registerFormDefinition": "{}",
            },
        )
        self.assertIsNotNone(result.data["adminObservationDefinitionUpdate"]["result"])
        self.assertIsNotNone(
            result.data["adminObservationDefinitionUpdate"]["result"]["fields"]
        )
        self.assertEqual(
            result.data["adminObservationDefinitionUpdate"]["result"]["fields"][0][
                "name"
            ],
            "name",
        )

    def test_update_success(self):
        mutation = """
        mutation adminObservationDefinitionUpdate($id: ID!, $name: String!, $description: String!, $titleTemplate: String!, $descriptionTemplate: String!, $identityTemplate: String!, $registerFormDefinition: JSONString!) {
            adminObservationDefinitionUpdate(id: $id, name: $name, description: $description, titleTemplate: $titleTemplate, descriptionTemplate: $descriptionTemplate, identityTemplate: $identityTemplate, registerFormDefinition: $registerFormDefinition) {
                result {
                  __typename
                  ... on AdminObservationDefinitionUpdateSuccess {
                    definition {
                        name
                        id
                        name
                    }
                  }
                  ... on AdminObservationDefinitionUpdateProblem {
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
                "id": self.definition1.id,
                "name": "definition other",
                "description": "description other",
                "titleTemplate": "titleTemplate other",
                "descriptionTemplate": "descriptionTemplate other",
                "identityTemplate": "identityTemplate other",
                "registerFormDefinition": "{}",
            },
        )
        self.assertIsNotNone(result.data["adminObservationDefinitionUpdate"]["result"])
        self.assertIsNotNone(
            result.data["adminObservationDefinitionUpdate"]["result"]["definition"][
                "id"
            ]
        )
        self.assertEqual(
            result.data["adminObservationDefinitionUpdate"]["result"]["definition"][
                "name"
            ],
            "definition other",
        )
