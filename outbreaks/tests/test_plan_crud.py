from graphql_jwt.testcases import JSONWebTokenTestCase

from accounts.models import User
from cases.models import StateDefinition, StateStep
from outbreaks.models import Plan
from reports.models import ReportType, Category


class AdminPlanTests(JSONWebTokenTestCase):
    def setUp(self):
        self.super_user = User.objects.create_superuser(
            username="admin", is_superuser=True
        )
        self.client.authenticate(self.super_user)
        self.category = Category.objects.create(name="test category")
        self.report_type1 = ReportType.objects.create(
            name="report type 1", category=self.category, definition="{}"
        )

        self.state = StateDefinition.objects.create(name="test state")
        self.step1 = StateStep.objects.create(
            name="step 1",
            state_definition=self.state,
        )

        self.plan1 = Plan.objects.create(
            name="plan1",
            description="plan1 description",
            report_type=self.report_type1,
            state_step=self.step1,
        )
        self.plan2 = Plan.objects.create(
            name="plan2",
            description="plan2 description",
            report_type=self.report_type1,
            state_step=self.step1,
        )

    def test_all_query(self):
        query = """
        query adminOutbreakPlanQuery {
            adminOutbreakPlanQuery {
                results {
                    id
                    name
                    description
                }
            }
        }
        """
        result = self.client.execute(query, {})
        self.assertEqual(len(result.data["adminOutbreakPlanQuery"]["results"]), 2)

    def test_filter_query(self):
        query = """
        query adminOutbreakPlanQuery($q: String) {
            adminOutbreakPlanQuery(q: $q) {
                results {
                    id
                    name
                    description
                }
            }
        }
        """
        result = self.client.execute(query, {"q": "plan1"})
        self.assertEqual(len(result.data["adminOutbreakPlanQuery"]["results"]), 1)

    def test_create(self):
        mutation = """
        mutation adminOutbreakPlanCreate($name: String!, $description: String!, $reportTypeId: UUID!, $stateStepId: Int!) {
            adminOutbreakPlanCreate(name: $name, description: $description, reportTypeId: $reportTypeId, stateStepId: $stateStepId) {
                result {
                    __typename
                    ... on AdminOutbreakPlanCreateSuccess {                    
                        id
                        name
                        description
                    }
                    ... on AdminOutbreakPlanCreateProblem {
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
                "name": "plan3",
                "description": "plan3 description",
                "reportTypeId": str(self.report_type1.id),
                "stateStepId": self.step1.id,
            },
        )
        self.assertEqual(
            result.data["adminOutbreakPlanCreate"]["result"]["name"], "plan3"
        )

    def test_update(self):
        mutation = """
        mutation adminOutbreakPlanUpdate($id: Int!, $name: String!, $description: String!, $reportTypeId: UUID!, 
            $stateStepId: Int!,
            $zone1Radius: Float, $zone1Color: String, $zone1MessageBody: String,
            $zone2Radius: Float, $zone2Color: String, $zone2MessageBody: String,
            $zone3Radius: Float, $zone3Color: String, $zone3MessageBody: String,
        ) {
            adminOutbreakPlanUpdate(id: $id, name: $name, description: $description, reportTypeId: $reportTypeId, stateStepId: $stateStepId,
                zone1Radius: $zone1Radius, zone1Color: $zone1Color, zone1MessageBody: $zone1MessageBody,
                zone2Radius: $zone2Radius, zone2Color: $zone2Color, zone2MessageBody: $zone2MessageBody,
                zone3Radius: $zone3Radius, zone3Color: $zone3Color, zone3MessageBody: $zone3MessageBody,
            ) {
                result {
                    __typename
                    ... on AdminOutbreakPlanUpdateSuccess {
                        id
                        name
                        description
                        }
                    ... on AdminOutbreakPlanUpdateProblem {
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
                "id": self.plan1.id,
                "name": "plan1_update",
                "description": "plan1 description update",
                "reportTypeId": str(self.report_type1.id),
                "stateStepId": self.step1.id,
                "zone1Radius": 100,
                "zone1Color": "#000000",
                "zone1MessageBody": "zone1",
                "zone2Radius": 200,
                "zone2Color": "#111111",
                "zone2MessageBody": "zone2",
                "zone3Radius": 300,
                "zone3Color": "#333333",
                "zone3MessageBody": "zone3",
            },
        )
        print(result)
        self.assertEqual(
            result.data["adminOutbreakPlanUpdate"]["result"]["name"], "plan1_update"
        )

    def test_delete(self):
        mutation = """
        mutation adminOutbreakPlanDelete($id: Int!) {
            adminOutbreakPlanDelete(id: $id) {
                success
            }
        }"""
        result = self.client.execute(mutation, {"id": self.plan1.id})
        self.assertEqual(result.data["adminOutbreakPlanDelete"]["success"], True)
        self.assertEqual(1, Plan.objects.count())
