from podd_api.celery import app

from cases.models import CaseDefinition, Case
from cases.tasks import evaluate_case_definition
from cases.tests.base_testcase import BaseTestCase


class CaseDefinitionTestCase(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.mers_definition = CaseDefinition.objects.create(
            report_type=self.mers_report_type,
            description="mers definition",
            is_active=True,
            condition="data.symptom == 'fever' and data.traveling is True",
        )
        app.conf.update(CELERY_ALWAYS_EAGER=True)

    def test_condition_evaluation_success(self):
        evaluate_case_definition(self.mers_report.id)
        self.assertTrue(Case.objects.filter(report_id=self.mers_report.id).exists())

    def test_condition_evaluation_not_success(self):
        self.mers_definition.condition = (
            "data.symptom == 'sore throat' and data.traveling is True"
        )
        self.mers_definition.save()
        evaluate_case_definition(self.mers_report.id)
        self.assertFalse(Case.objects.filter(report_id=self.mers_report.id).exists())
