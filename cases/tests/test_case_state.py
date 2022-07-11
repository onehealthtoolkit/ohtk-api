from cases.models import (
    StateDefinition,
    StateStep,
    StateTransition,
    Case,
    CaseState,
)
from cases.tests.base_testcase import BaseTestCase
from reports.models import ReportType


class CaseStateTestCase(BaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.animal_bite = ReportType.objects.create(
            name="animal bite", definition={}, category=self.animal_category
        )

    def test_resolve_case_definition(self):
        resolve_definition = StateDefinition.resolve(self.mers_report_type.id)
        self.assertEqual(resolve_definition.id, self.mers_state_definition.id)

        resolve_definition = StateDefinition.resolve(self.animal_bite.id)
        self.assertEqual(resolve_definition.id, self.default_state_definition.id)

    def test_create_case_state_with_start_step(self):
        report = self.mers_report
        case = Case.promote_from_incident_report(report.id)
        states = CaseState.objects.filter(case=case)
        self.assertEqual(1, len(states))

    def test_flow_from_step1_to_step2(self):
        report = self.mers_report
        case = Case.promote_from_incident_report(report.id)
        states = case.current_states
        self.assertEqual(1, len(states))
        step1_instance = states[0]
        self.assertEqual(self.step1.name, step1_instance.state.name)
        step2_instance = case.forward_state(
            from_step_id=step1_instance.state.id,
            to_step_id=self.step2.id,
            form_data={},
            created_by=self.user,
        )
        self.assertEqual(self.step2.name, step2_instance.state.name)
        step1_instance.refresh_from_db()
        self.assertIsNotNone(step1_instance.transition)
        self.assertEqual(step1_instance.transition.created_by.id, self.user.id)

        states = case.current_states
        self.assertEqual(1, len(states))

        self.assertEqual(2, CaseState.objects.filter(case_id=case.id).count())
