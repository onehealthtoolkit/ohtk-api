from django.utils.timezone import now

from reports.models import IncidentReport
from reports.test.base_testcase import BaseTestCase


class IncidentReportTestCase(BaseTestCase):
    def test_create_report(self):
        self.mers_report_type.renderer_data_template = (
            """found {{ number_of_sick }} with symptom: {{ symptom }}"""
        )
        self.mers_report_type.save()

        report = IncidentReport.objects.create(
            data={
                "symptom": "cough",
                "number_of_sick": 1,
            },
            reported_by=self.user,
            incident_date=now(),
            report_type=self.mers_report_type,
        )
        self.assertIsNotNone(report.id)
        self.assertEqual("found 1 with symptom: cough", report.renderer_data)
