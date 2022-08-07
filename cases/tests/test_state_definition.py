from django.test import TestCase

from cases.models import StateDefinition, StateStep, StateTransition, CaseStateMapping
from reports.models import ReportType, Category


class StateDefinitionTestCase(TestCase):
    def setUp(self):
        category = Category.objects.create(name="human")
        self.report_type = ReportType.objects.create(
            name="sick/death", definition={}, category=category
        )
        self.definition = StateDefinition.objects.create(
            name="default state definition"
        )

        self.step1 = StateStep.objects.create(
            name="step1", is_start_state=True, state_definition=self.definition
        )

        self.step2 = StateStep.objects.create(
            name="step2", state_definition=self.definition
        )

        self.step3 = StateStep.objects.create(
            name="step3", is_stop_state=True, state_definition=self.definition
        )
        self.transition1 = StateTransition.objects.create(
            from_step=self.step1, to_step=self.step2
        )
        self.transition2 = StateTransition.objects.create(
            from_step=self.step2, to_step=self.step3
        )

    def test_definition_model(self):
        definition = StateDefinition.objects.create(name="default state definition")
        self.assertFalse(definition.is_default)

        step1 = StateStep.objects.create(
            name="step1", is_start_state=True, state_definition=definition
        )
        self.assertFalse(step1.is_stop_state)

        step2 = StateStep.objects.create(name="step2", state_definition=definition)
        self.assertFalse(step2.is_start_state)
        self.assertFalse(step2.is_stop_state)

        step3 = StateStep.objects.create(
            name="step3", is_stop_state=True, state_definition=definition
        )
        self.assertFalse(step3.is_start_state)

        self.assertEqual(3, definition.statestep_set.count())

        transition1 = StateTransition.objects.create(from_step=step1, to_step=step2)
        transition2 = StateTransition.objects.create(from_step=step2, to_step=step3)
        transition3 = StateTransition.objects.create(from_step=step1, to_step=step3)

        self.assertEquals(2, step1.to_transitions.count())
        self.assertEqual(1, step2.to_transitions.count())
        self.assertEqual(2, step3.from_transitions.count())
        self.assertEqual(0, step3.to_transitions.count())

    def test_definition_mapping(self):
        definition = StateDefinition.objects.create(name="default state definition")
        CaseStateMapping.objects.create(
            report_type=self.report_type, state_definition=definition
        )

    def test_definition_mapping_unique(self):
        definition = StateDefinition.objects.create(name="default state definition")

        CaseStateMapping.objects.create(
            report_type=self.report_type, state_definition=definition
        )

        try:
            CaseStateMapping.objects.create(
                report_type=self.report_type, state_definition=definition
            )
            raise "should not be here"
        except:
            pass

    def test_delete_definition(self):
        self.definition.delete()
        self.assertEqual(StateTransition.objects.count(), 0)
        self.assertEqual(StateStep.objects.count(), 0)
        self.assertEqual(StateDefinition.objects.count(), 0)

    def test_delete_step(self):
        self.assertEqual(StateTransition.objects.count(), 2)
        self.assertEqual(StateStep.objects.count(), 3)
        self.step1.delete()
        self.assertEqual(StateStep.objects.count(), 2)
        self.assertEqual(StateTransition.objects.count(), 1)
        self.assertEqual(StateTransition.objects.first().id, self.transition2.id)
