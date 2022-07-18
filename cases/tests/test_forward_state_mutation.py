from cases.models import Case, CaseState
from cases.tests.base_testcase import BaseTestCase


class ForwardStateMutationTestCase(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.case = Case.promote_from_incident_report(self.mers_report.id)

    def test_forward_state(self):
        mutation = """
            mutation forwardState($caseId: ID!, $transitionId: ID!, $formData: GenericScalar) {
              forwardState(caseId: $caseId, transitionId: $transitionId, formData: $formData) {
                result {     
                    id               
                    state {
                        id
                        name
                        toTransitions {
                            toStep {
                                name
                            }
                        }
                    }                                        
                }
              }
            }
        """

        result = self.client.execute(
            mutation,
            {
                "caseId": str(self.case.id),
                "transitionId": self.transition1.id,
                "formData": {"x": 2},
            },
        )
        print(result)
        self.assertIsNotNone(result.data["forwardState"]["result"])
        self.assertIsNotNone(result.data["forwardState"]["result"]["state"])
        caseStateId = result.data["forwardState"]["result"]["id"]
        cs = CaseState.objects.get(pk=caseStateId)
