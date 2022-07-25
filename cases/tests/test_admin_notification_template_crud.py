import uuid
from graphql_jwt.testcases import JSONWebTokenTestCase

from cases.models import (
    NotificationTemplate,
    StateDefinition,
    StateStep,
    StateTransition,
)
from reports.models.category import Category
from reports.models.report_type import ReportType


class AdminNotificationTemplateTests(JSONWebTokenTestCase):
    def setUp(self):
        self.category = Category.objects.create(name="report category1", ordering=1)
        self.reportType = ReportType.objects.create(
            name="report type1",
            category=self.category,
            definition='{"x":"YYY"}',
            ordering=1,
        )
        self.stateDefinition = StateDefinition.objects.create(
            name="stateDefinition",
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
        self.stateTransition = StateTransition.objects.create(
            from_step=self.fromStep,
            to_step=self.toStep,
            form_definition='{"x":"x-value"}',
        )
        self.notification_template1 = NotificationTemplate.objects.create(
            name="Notification1",
            state_transition=self.stateTransition,
            report_type=self.reportType,
            title_template="Notification from podd",
            body_template="You have new messages {{total}}",
        )

        self.notification_template2 = NotificationTemplate.objects.create(
            name="Notification2",
            state_transition=self.stateTransition,
            report_type=self.reportType,
            title_template="Notification from podd2",
            body_template="You job is close {{total}}",
        )

    def test_simple_query(self):
        query = """
        query adminNotificationTemplateQuery {
            adminNotificationTemplateQuery {
                results {
                    id
                    name
                }
            }
        }
        """
        result = self.client.execute(query, {})
        self.assertEqual(
            len(result.data["adminNotificationTemplateQuery"]["results"]), 2
        )

    def test_query_with_name(self):
        query = """
        query adminNotificationTemplateQuery($name: String) {
            adminNotificationTemplateQuery(name: $name) {
                results {
                    id
                    name
                }
            }
        }
        """
        result = self.client.execute(query, {"name": "Notification1"})
        self.assertEqual(
            len(result.data["adminNotificationTemplateQuery"]["results"]), 1
        )

    def test_create_with_error(self):
        mutation = """
        mutation adminNotificationTemplateCreate($name: String!, $stateTransitionId: Int!, $reportTypeId: UUID!, $titleTemplate: String!, $bodyTemplate: String!) {
            adminNotificationTemplateCreate(name: $name, stateTransitionId: $stateTransitionId, reportTypeId: $reportTypeId, titleTemplate: $titleTemplate, bodyTemplate: $bodyTemplate) {
                result {
                  __typename
                  ... on AdminNotificationTemplateCreateSuccess {
                    id
                    name
                  }
                  ... on AdminNotificationTemplateCreateProblem {
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
                "name": "Notification1",
                "stateTransitionId": self.stateTransition.id,
                "reportTypeId": str(self.reportType.id),
                "titleTemplate": "This message title",
                "bodyTemplate": "The body template testing",
            },
        )
        self.assertIsNotNone(result.data["adminNotificationTemplateCreate"]["result"])
        self.assertIsNotNone(
            result.data["adminNotificationTemplateCreate"]["result"]["fields"]
        )
        self.assertEqual(
            result.data["adminNotificationTemplateCreate"]["result"]["__typename"],
            "AdminNotificationTemplateCreateProblem",
        )
        self.assertEqual(
            result.data["adminNotificationTemplateCreate"]["result"]["fields"][0][
                "name"
            ],
            "name",
        )

    def test_create_success(self):
        mutation = """
        mutation adminNotificationTemplateCreate($name: String!, $stateTransitionId: Int!, $reportTypeId: UUID!, $titleTemplate: String!, $bodyTemplate: String!) {
            adminNotificationTemplateCreate(name: $name, stateTransitionId: $stateTransitionId, reportTypeId: $reportTypeId, titleTemplate: $titleTemplate, bodyTemplate: $bodyTemplate) {
                result {
                  __typename
                  ... on AdminNotificationTemplateCreateSuccess {
                    id
                    name
                  }
                  ... on AdminNotificationTemplateCreateProblem {
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
                "name": "Notification3",
                "stateTransitionId": self.stateTransition.id,
                "reportTypeId": str(self.reportType.id),
                "titleTemplate": "This message title",
                "bodyTemplate": "The body template testing",
            },
        )
        self.assertIsNotNone(result.data["adminNotificationTemplateCreate"]["result"])
        self.assertIsNotNone(
            result.data["adminNotificationTemplateCreate"]["result"]["id"]
        )
        self.assertEqual(
            result.data["adminNotificationTemplateCreate"]["result"]["name"],
            "Notification3",
        )

    def test_update_with_error(self):
        mutation = """
        mutation adminNotificationTemplateUpdate($id: ID!, $name: String!, $stateTransitionId: Int!, $reportTypeId: UUID!, $titleTemplate: String!, $bodyTemplate: String!) {
            adminNotificationTemplateUpdate(id: $id, name: $name, stateTransitionId: $stateTransitionId, reportTypeId: $reportTypeId, titleTemplate: $titleTemplate, bodyTemplate: $bodyTemplate) {
                result {
                  __typename
                  ... on AdminNotificationTemplateUpdateSuccess {
                    notificationTemplate {
                      id
                      name
                    }
                  }
                  ... on AdminNotificationTemplateUpdateProblem {
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
                "id": self.notification_template1.id,
                "name": "Notification2",
                "stateTransitionId": self.stateTransition.id,
                "reportTypeId": str(self.reportType.id),
                "titleTemplate": "This message title",
                "bodyTemplate": "The body template testing",
            },
        )
        print(result)
        self.assertIsNotNone(result.data["adminNotificationTemplateUpdate"]["result"])
        self.assertIsNotNone(
            result.data["adminNotificationTemplateUpdate"]["result"]["fields"]
        )
        self.assertEqual(
            result.data["adminNotificationTemplateUpdate"]["result"]["__typename"],
            "AdminNotificationTemplateUpdateProblem",
        )

    def test_update_success(self):
        mutation = """
        mutation adminNotificationTemplateUpdate($id: ID!, $name: String!, $stateTransitionId: Int!, $reportTypeId: UUID!, $titleTemplate: String!, $bodyTemplate: String!) {
            adminNotificationTemplateUpdate(id: $id, name: $name, stateTransitionId: $stateTransitionId, reportTypeId: $reportTypeId, titleTemplate: $titleTemplate, bodyTemplate: $bodyTemplate) {
                result {
                  __typename
                  ... on AdminNotificationTemplateUpdateSuccess {
                    notificationTemplate {
                      id
                      name
                    }
                  }
                  ... on AdminNotificationTemplateUpdateProblem {
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
                "id": self.notification_template1.id,
                "name": "Notification3",
                "stateTransitionId": self.stateTransition.id,
                "reportTypeId": str(self.reportType.id),
                "titleTemplate": "This message title",
                "bodyTemplate": "The body template testing",
            },
        )
        self.assertIsNotNone(result.data["adminNotificationTemplateUpdate"]["result"])
        self.assertIsNotNone(
            result.data["adminNotificationTemplateUpdate"]["result"][
                "notificationTemplate"
            ]["id"]
        )
        self.assertEqual(
            result.data["adminNotificationTemplateUpdate"]["result"][
                "notificationTemplate"
            ]["name"],
            "Notification3",
        )
