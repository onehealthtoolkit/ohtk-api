import uuid
from graphql_jwt.testcases import JSONWebTokenTestCase
from accounts.models import User

from cases.models import StateDefinition, StateStep
from reports.models.report_type import ReportType


class AdminStateStepTests(JSONWebTokenTestCase):
    def setUp(self):
        self.stateDefinition = StateDefinition.objects.create(
            name="stateDefinition1",
            is_default=True,
        )
        self.stateStep1 = StateStep.objects.create(
            name="stateStep1",
            is_start_state=True,
            is_stop_state=False,
            state_definition=self.stateDefinition,
        )
        self.stateStep2 = StateStep.objects.create(
            name="stateStep2",
            is_start_state=False,
            is_stop_state=True,
            state_definition=self.stateDefinition,
        )
        self.user = User.objects.create(username="admintest", is_superuser=True)
        self.client.authenticate(self.user)

    def test_query_with_definition_id(self):
        query = """
        query adminStateStepQuery($definitionId: ID!) {
            adminStateStepQuery(definitionId: $definitionId) {
                id
                name
            }
        }
        """
        result = self.client.execute(query, {"definitionId": self.stateDefinition.id})
        self.assertEqual(len(result.data["adminStateStepQuery"]), 2)

    def test_create_with_error(self):
        mutation = """
        mutation adminStateStepCreate($name: String!, $isStartState: Boolean!, $isStopState:Boolean!, $stateDefinitionId:ID!) {
            adminStateStepCreate(name: $name, isStartState: $isStartState, isStopState:$isStopState, stateDefinitionId:$stateDefinitionId) {
                result {
                  __typename
                  ... on AdminStateStepCreateSuccess {
                    id
                    name
                  }
                  ... on AdminStateStepCreateProblem {
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
                "name": "",
                "isStartState": True,
                "isStopState": True,
                "stateDefinitionId": self.stateDefinition.id,
            },
        )
        self.assertIsNotNone(result.data["adminStateStepCreate"]["result"])
        self.assertIsNotNone(result.data["adminStateStepCreate"]["result"]["fields"])
        self.assertEqual(
            result.data["adminStateStepCreate"]["result"]["__typename"],
            "AdminStateStepCreateProblem",
        )

    def test_create_success(self):
        mutation = """
        mutation adminStateStepCreate($name: String!, $isStartState: Boolean!, $isStopState:Boolean!, $stateDefinitionId:ID!) {
            adminStateStepCreate(name: $name, isStartState: $isStartState, isStopState:$isStopState, stateDefinitionId:$stateDefinitionId) {
                result {
                  __typename
                  ... on AdminStateStepCreateSuccess {
                    id
                    name
                  }
                  ... on AdminStateStepCreateProblem {
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
                "name": "stateStep3",
                "isStartState": True,
                "isStopState": True,
                "stateDefinitionId": self.stateDefinition.id,
            },
        )
        self.assertIsNotNone(result.data["adminStateStepCreate"]["result"])
        self.assertIsNotNone(result.data["adminStateStepCreate"]["result"]["id"])
        self.assertEqual(
            result.data["adminStateStepCreate"]["result"]["name"],
            "stateStep3",
        )

    def test_update_with_error(self):
        mutation = """
        mutation adminStateStepUpdate($id: ID!, $name: String!, $isStartState: Boolean!, $isStopState:Boolean!, $stateDefinitionId:ID!) {
            adminStateStepUpdate(id: $id, name: $name, isStartState: $isStartState, isStopState:$isStopState, stateDefinitionId:$stateDefinitionId) {
                result {
                  __typename
                  ... on AdminStateStepUpdateSuccess {
                    stateStep {
                      id
                      name
                    }
                  }
                  ... on AdminStateStepUpdateProblem {
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
                "id": self.stateStep1.id,
                "name": "",
                "isStartState": True,
                "isStopState": True,
                "stateDefinitionId": self.stateDefinition.id,
            },
        )

        self.assertIsNotNone(result.data["adminStateStepUpdate"]["result"])
        self.assertIsNotNone(result.data["adminStateStepUpdate"]["result"]["fields"])
        self.assertEqual(
            result.data["adminStateStepUpdate"]["result"]["__typename"],
            "AdminStateStepUpdateProblem",
        )

    def test_update_success(self):
        mutation = """
        mutation adminStateStepUpdate($id: ID!, $name: String!, $isStartState: Boolean!, $isStopState:Boolean!, $stateDefinitionId:ID!) {
            adminStateStepUpdate(id: $id, name: $name, isStartState: $isStartState, isStopState:$isStopState, stateDefinitionId:$stateDefinitionId) {
                result {
                  __typename
                  ... on AdminStateStepUpdateSuccess {
                    stateStep {
                      id
                      name
                    }
                  }
                  ... on AdminStateStepUpdateProblem {
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
                "id": self.stateStep1.id,
                "name": "stateStep3",
                "isStartState": True,
                "isStopState": True,
                "stateDefinitionId": self.stateDefinition.id,
            },
        )

        self.assertIsNotNone(result.data["adminStateStepUpdate"]["result"])
        self.assertIsNotNone(
            result.data["adminStateStepUpdate"]["result"]["stateStep"]["id"]
        )
        self.assertEqual(
            result.data["adminStateStepUpdate"]["result"]["stateStep"]["name"],
            "stateStep3",
        )
