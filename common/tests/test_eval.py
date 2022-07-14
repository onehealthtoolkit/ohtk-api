from unittest import TestCase

from common.eval import build_eval_obj


class EvalTestCase(TestCase):
    def test_string_contain_function(self):
        context_obj = build_eval_obj({"symptoms": "cough, fever"})
        self.assertTrue(context_obj.eval("'fever' in symptoms"))

    def test_array_contain_function(self):
        context_obj = build_eval_obj({"symptoms": ["cough", "fever"]})
        self.assertTrue(context_obj.eval("'fever' in symptoms"))

    def test_boolean_operator(self):
        context_obj = build_eval_obj({"symptoms": {"cough": True, "fever": False}})
        self.assertTrue(context_obj.eval("symptoms.cough and not symptoms.fever"))

    def test_assignment(self):
        context_obj = build_eval_obj({"symptoms": {"cough": True, "fever": False}})
        context_obj.eval("set_data('test', True)")
        self.assertTrue(context_obj.eval("symptoms.cough and test"))
