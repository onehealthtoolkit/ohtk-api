from graphql_jwt.testcases import JSONWebTokenTestCase

from accounts.models import User
from observations.models import Definition, MonitoringDefinition


class AdminObservationMonitoringDefinitionTests(JSONWebTokenTestCase):
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

        self.monitoringDefinition1 = MonitoringDefinition.objects.create(
            definition=self.definition1,
            name="monitoringDefinition1",
            description="description1",
            is_active=True,
            form_definition="{}",
            title_template="title",
            description_template="template",
        )
        self.monitoringDefinition2 = MonitoringDefinition.objects.create(
            definition=self.definition1,
            name="monitoringDefinition2",
            description="description 2",
            is_active=True,
            form_definition="{}",
            title_template="title2",
            description_template="template 2",
        )
        self.user = User.objects.create(username="admintest", is_superuser=True)
        self.client.authenticate(self.user)

    def test_simple_query(self):
        query = """
        query adminObservationMonitoringDefinitionQuery($definitionId: ID!) {
            adminObservationMonitoringDefinitionQuery(definitionId: $definitionId) {
                id
                name
                description
            }
        }
        """
        result = self.client.execute(query, {"definitionId": self.definition1.id})
        self.assertEqual(
            len(result.data["adminObservationMonitoringDefinitionQuery"]), 2
        )

    def test_create_with_error(self):
        mutation = """
        mutation adminObservationMonitoringDefinitionCreate($definitionId: ID!, $name: String!, $description: String!, $titleTemplate: String!, $descriptionTemplate: String!, $formDefinition: JSONString!) {
            adminObservationMonitoringDefinitionCreate(definitionId: $definitionId, name: $name, description: $description, titleTemplate: $titleTemplate, descriptionTemplate: $descriptionTemplate, formDefinition: $formDefinition) {
                result {
                  __typename
                  ... on AdminObservationMonitoringDefinitionCreateSuccess {
                    name
                    id
                    createdAt
                  }
                  ... on AdminObservationMonitoringDefinitionCreateProblem {
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
                "definitionId": self.definition1.id,
                "name": "",
                "description": "description one",
                "titleTemplate": "titleTemplate",
                "descriptionTemplate": "descriptionTemplate",
                "formDefinition": "{}",
            },
        )
        self.assertIsNotNone(
            result.data["adminObservationMonitoringDefinitionCreate"]["result"]
        )
        self.assertIsNotNone(
            result.data["adminObservationMonitoringDefinitionCreate"]["result"][
                "fields"
            ]
        )
        self.assertEqual(
            result.data["adminObservationMonitoringDefinitionCreate"]["result"][
                "fields"
            ][0]["name"],
            "name",
        )

    def test_create_success(self):
        mutation = """
        mutation adminObservationMonitoringDefinitionCreate($definitionId: ID!, $name: String!, $description: String!, $titleTemplate: String!, $descriptionTemplate: String!, $formDefinition: JSONString!) {
            adminObservationMonitoringDefinitionCreate(definitionId: $definitionId, name: $name, description: $description, titleTemplate: $titleTemplate, descriptionTemplate: $descriptionTemplate, formDefinition: $formDefinition) {
                result {
                  __typename
                  ... on AdminObservationMonitoringDefinitionCreateSuccess {
                    name
                    id
                    createdAt
                  }
                  ... on AdminObservationMonitoringDefinitionCreateProblem {
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
                "definitionId": self.definition1.id,
                "name": "monitoringDefinition other",
                "description": "description other",
                "titleTemplate": "titleTemplate",
                "descriptionTemplate": "descriptionTemplate",
                "formDefinition": "{}",
            },
        )
        self.assertIsNotNone(
            result.data["adminObservationMonitoringDefinitionCreate"]["result"]
        )
        self.assertIsNotNone(
            result.data["adminObservationMonitoringDefinitionCreate"]["result"]["id"]
        )
        self.assertEqual(
            result.data["adminObservationMonitoringDefinitionCreate"]["result"]["name"],
            "monitoringDefinition other",
        )

    def test_update_with_error(self):
        mutation = """
        mutation adminObservationMonitoringDefinitionUpdate($id: ID!, $definitionId: ID!, $name: String!, $description: String!, $titleTemplate: String!, $descriptionTemplate: String!, $formDefinition: JSONString!) {
            adminObservationMonitoringDefinitionUpdate(id: $id, definitionId: $definitionId, name: $name, description: $description, titleTemplate: $titleTemplate, descriptionTemplate: $descriptionTemplate, formDefinition: $formDefinition) {
                result {
                  __typename
                  ... on AdminObservationMonitoringDefinitionUpdateSuccess {
                    monitoringDefinition {
                        name
                        id
                        name
                    }
                  }
                  ... on AdminObservationMonitoringDefinitionUpdateProblem {
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
                "id": self.monitoringDefinition1.id,
                "definitionId": self.definition1.id,
                "name": "",
                "description": "description other",
                "titleTemplate": "titleTemplate",
                "descriptionTemplate": "descriptionTemplate",
                "formDefinition": "{}",
            },
        )
        self.assertIsNotNone(
            result.data["adminObservationMonitoringDefinitionUpdate"]["result"]
        )
        self.assertIsNotNone(
            result.data["adminObservationMonitoringDefinitionUpdate"]["result"][
                "fields"
            ]
        )
        self.assertEqual(
            result.data["adminObservationMonitoringDefinitionUpdate"]["result"][
                "fields"
            ][0]["name"],
            "name",
        )

    def test_update_success(self):
        mutation = """
        mutation adminObservationMonitoringDefinitionUpdate($id: ID!, $definitionId: ID!, $name: String!, $description: String!, $titleTemplate: String!, $descriptionTemplate: String!, $formDefinition: JSONString!) {
            adminObservationMonitoringDefinitionUpdate(id: $id, definitionId: $definitionId, name: $name, description: $description, titleTemplate: $titleTemplate, descriptionTemplate: $descriptionTemplate, formDefinition: $formDefinition) {
                result {
                  __typename
                  ... on AdminObservationMonitoringDefinitionUpdateSuccess {
                    monitoringDefinition {
                        name
                        id
                        name
                    }
                  }
                  ... on AdminObservationMonitoringDefinitionUpdateProblem {
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
                "id": self.monitoringDefinition1.id,
                "definitionId": self.definition1.id,
                "name": "Monitoring Definition other",
                "description": "description other",
                "titleTemplate": "titleTemplate",
                "descriptionTemplate": "descriptionTemplate",
                "formDefinition": "{}",
            },
        )
        self.assertIsNotNone(
            result.data["adminObservationMonitoringDefinitionUpdate"]["result"]
        )
        self.assertIsNotNone(
            result.data["adminObservationMonitoringDefinitionUpdate"]["result"][
                "monitoringDefinition"
            ]["id"]
        )
        self.assertEqual(
            result.data["adminObservationMonitoringDefinitionUpdate"]["result"][
                "monitoringDefinition"
            ]["name"],
            "Monitoring Definition other",
        )
