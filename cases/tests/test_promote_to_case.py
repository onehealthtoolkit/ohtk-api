from cases.models import Case
from .base_testcase import BaseTestCase


class PromoteToCaseTests(BaseTestCase):
    def setUp(self) -> None:
        super().setUp()

    def test_promote_to_case_with_default_mapping(self):
        mutation = """
            mutation promoteToCase($reportId: UUID!) {
                promoteToCase(reportId: $reportId) {
                    report {
                        caseId
                    }
                    case {
                        id
                    }
                }
            }        
        """
        result = self.client.execute(mutation, {"reportId": str(self.dengue_report.id)})
        self.assertIsNotNone(result.data["promoteToCase"]["report"])
        self.assertIsNotNone(result.data["promoteToCase"]["report"]["caseId"])
        case = Case.objects.filter(report=self.dengue_report).first()
        self.assertEqual(result.data["promoteToCase"]["report"]["caseId"], str(case.id))

    def test_promote_to_case_with_exiting_mapping(self):
        mutation = """
                    mutation promoteToCase($reportId: UUID!) {
                        promoteToCase(reportId: $reportId) {
                            report {
                                caseId
                            }
                            case {
                                id
                            }
                        }
                    }        
                """
        result = self.client.execute(mutation, {"reportId": str(self.mers_report.id)})
        self.assertIsNotNone(result.data["promoteToCase"]["report"])
        self.assertIsNotNone(result.data["promoteToCase"]["report"]["caseId"])
        case = Case.objects.filter(report=self.mers_report).first()
        self.assertEqual(case.status_template_id, self.mers_template.id)
