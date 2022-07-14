from django.utils.timezone import now

from reports.models import IncidentReport
from reports.tests.base_testcase import BaseTestCase


class EvaluateConditionTestCase(BaseTestCase):
    def test_evaluate_report_data(self):
        report = IncidentReport.objects.create(
            data={
                "symptom": "cough",
                "number_of_sick": 1,
            },
            reported_by=self.user,
            incident_date=now(),
            report_type=self.mers_report_type,
        )
        context = report.evaluate_context()
        self.assertTrue(context.eval("data.symptom == 'cough'"))
        self.assertFalse(
            context.eval("data.symptom == 'cough' and data.number_of_sick > 5")
        )
        self.assertTrue(
            context.eval("data.symptom == 'cough' and data.number_of_sick < 5")
        )
