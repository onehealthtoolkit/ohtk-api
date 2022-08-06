import json
import uuid
from graphql_jwt.testcases import JSONWebTokenTestCase
from accounts.models import User

from cases.models import StateDefinition, StateStep, StateTransition
from reports.models.report_type import ReportType


class AdminStateTransitionTests(JSONWebTokenTestCase):
    def setUp(self):
        self.stateDefinition = StateDefinition.objects.create(
            name="stateDefinition1",
            is_default=True,
        )
        self.fromStep = StateStep.objects.create(
            name="fromStep",
            is_start_state=True,
            is_stop_state=False,
            state_definition=self.stateDefinition,
        )
        self.toStep = StateStep.objects.create(
            name="toStep",
            is_start_state=False,
            is_stop_state=True,
            state_definition=self.stateDefinition,
        )
        self.stateTransition1 = StateTransition.objects.create(
            from_step=self.fromStep,
            to_step=self.toStep,
            form_definition='{"x":"x-value"}',
        )
        self.stateTransition2 = StateTransition.objects.create(
            from_step=self.fromStep,
            to_step=self.toStep,
            form_definition='{"y":"y-value"}',
        )
        self.user = User.objects.create(username="admintest", is_superuser=True)
        self.client.authenticate(self.user)

    def test_query_with_definition_id(self):
        query = """
        query adminStateTransitionQuery($definitionId: ID!) {
            adminStateTransitionQuery(definitionId: $definitionId) {
                id
            }
        }
        """
        result = self.client.execute(query, {"definitionId": self.stateDefinition.id})
        self.assertEqual(len(result.data["adminStateTransitionQuery"]), 2)

    def test_create_with_error(self):
        mutation = """
        mutation adminStateTransitionCreate($formDefinition: String!, $fromStepId: ID!, $toStepId: ID!) {
            adminStateTransitionCreate(formDefinition: $formDefinition, fromStepId: $fromStepId, toStepId: $toStepId) {
                result {
                  __typename
                  ... on AdminStateTransitionCreateSuccess {
                    id
                  }
                  ... on AdminStateTransitionCreateProblem {
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
                "formDefinition": "",
                "fromStepId": self.fromStep.id,
                "toStepId": self.fromStep.id,
            },
        )
        self.assertIsNotNone(result.data["adminStateTransitionCreate"]["result"])
        self.assertIsNotNone(
            result.data["adminStateTransitionCreate"]["result"]["fields"]
        )
        self.assertEqual(
            result.data["adminStateTransitionCreate"]["result"]["__typename"],
            "AdminStateTransitionCreateProblem",
        )

    def test_create_success(self):
        mutation = """
        mutation adminStateTransitionCreate($formDefinition: String!, $fromStepId: ID!, $toStepId: ID!) {
            adminStateTransitionCreate(formDefinition: $formDefinition, fromStepId: $fromStepId, toStepId: $toStepId) {
                result {
                  __typename
                  ... on AdminStateTransitionCreateSuccess {
                    id
                    formDefinition
                  }
                  ... on AdminStateTransitionCreateProblem {
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
                "formDefinition": '{"z":"z-value"}',
                "fromStepId": self.fromStep.id,
                "toStepId": self.fromStep.id,
            },
        )
        self.assertIsNotNone(result.data["adminStateTransitionCreate"]["result"])
        self.assertIsNotNone(result.data["adminStateTransitionCreate"]["result"]["id"])
        self.assertEqual(
            json.loads(
                result.data["adminStateTransitionCreate"]["result"]["formDefinition"]
            )["z"],
            "z-value",
        )

    def test_update_with_error(self):
        mutation = """
        mutation adminStateTransitionUpdate($id: ID!, $formDefinition: String!, $fromStepId: ID!, $toStepId: ID!) {
            adminStateTransitionUpdate(id: $id, formDefinition: $formDefinition, fromStepId: $fromStepId, toStepId: $toStepId) {
                result {
                  __typename
                  ... on AdminStateTransitionUpdateSuccess {
                    stateTransition {
                      id
                      formDefinition
                    }
                  }
                  ... on AdminStateTransitionUpdateProblem {
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
                "id": self.stateTransition1.id,
                "formDefinition": "",
                "fromStepId": self.fromStep.id,
                "toStepId": self.fromStep.id,
            },
        )
        self.assertIsNotNone(result.data["adminStateTransitionUpdate"]["result"])
        self.assertIsNotNone(
            result.data["adminStateTransitionUpdate"]["result"]["fields"]
        )
        self.assertEqual(
            result.data["adminStateTransitionUpdate"]["result"]["__typename"],
            "AdminStateTransitionUpdateProblem",
        )

    def test_update_success(self):
        mutation = """
        mutation adminStateTransitionUpdate($id: ID!, $formDefinition: String!, $fromStepId: ID!, $toStepId: ID!) {
            adminStateTransitionUpdate(id: $id, formDefinition: $formDefinition, fromStepId: $fromStepId, toStepId: $toStepId) {
                result {
                  __typename
                  ... on AdminStateTransitionUpdateSuccess {
                    stateTransition {
                      id
                      formDefinition
                    }
                  }
                  ... on AdminStateTransitionUpdateProblem {
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
                "id": self.stateTransition1.id,
                "formDefinition": '{"a":"a-value"}',
                "fromStepId": self.fromStep.id,
                "toStepId": self.fromStep.id,
            },
        )

        self.assertIsNotNone(result.data["adminStateTransitionUpdate"]["result"])
        self.assertIsNotNone(
            result.data["adminStateTransitionUpdate"]["result"]["stateTransition"]["id"]
        )
        self.assertEqual(
            result.data["adminStateTransitionUpdate"]["result"]["stateTransition"][
                "formDefinition"
            ]["a"],
            "a-value",
        )
