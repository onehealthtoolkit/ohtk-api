from unittest import TestCase

from simpleeval import SimpleEval

from common.eval import build_eval_obj, FormData


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


class FormDataTestCase(TestCase):
    def test_attribute_access(self):
        data = {"symptoms": {"cough": True, "fever": False}}
        form_data = FormData(data)
        self.assertTrue(form_data.symptoms.cough)
        self.assertTrue(form_data["symptoms"]["cough"])

    def test_field_ends_with(self):
        data = {
            "gender": "male",
            "poultry_disease__value": "a",
            "poultry_disease": {
                "value": "a",
                "a": True,
                "b": False,
            },
            "dog_disease__value": "c,d",
            "dog_disease": {
                "value": "c,d",
                "c": True,
                "d": True,
                "e": False,
            },
        }
        form_data = FormData(data)
        self.assertTrue(
            any(
                form_data.fields_end_with("_disease__value")
                .exclude_value("ระบุอาการ")
                .values()
            )
        )

    def test_field_ends_with2(self):
        data = {
            "gender": "male",
            "dog_disease__value": "ระบุอาการ",
            "dog_symptom": {
                "value": "c,d",
                "c": True,
                "d": True,
                "e": False,
            },
        }
        form_data = FormData(data)
        self.assertFalse(
            any(
                form_data.fields_end_with("_disease__value")
                .exclude_value("ระบุอาการ")
                .values()
            )
        )

    def test_via_simple_eval(self):
        data = {
            "gender": "male",
            "poultry_disease__value": "a",
            "poultry_disease": {
                "value": "a",
                "a": True,
                "b": False,
            },
            "dog_disease__value": "c,d",
            "dog_disease": {
                "value": "c,d",
                "c": True,
                "d": True,
                "e": False,
            },
        }

        s = SimpleEval()
        form_data = FormData(data)
        s.names = {"form_data": form_data}
        s.functions = {"any": any}
        self.assertTrue(
            s.eval(
                """any(
                        form_data.fields_end_with("_disease__value") 
                        .exclude_value("ระบุอาการ") 
                        .values()
                )"""
            )
        )

        self.assertTrue(
            s.eval(
                """form_data.fields_end_with("_disease__value").exclude_value("ระบุอาการ").exists()"""
            )
        )

    def test_contains_value_true(self):
        data = {
            "animal_type": "หมู วัว ควาย",
            "swine_skin_symptoms__value": "มีตุ่มน้ำใส/แผลที่ปาก,แผลเรื้อรัง",
            "swine_general_symptoms__value": "ตายเฉียบพลัน",
            "swine_test_symptoms__value": "anyvalue",
        }

        form_data = FormData(data)
        self.assertTrue(
            form_data.fields_end_with("_symptoms__value").contains_value(
                "มีตุ่มน้ำใส/แผลที่ปาก", "ตายเฉียบพลัน"
            )
        )
        self.assertTrue(
            form_data.fields_end_with("_symptoms__value").contains_value(
                "มีตุ่มน้ำใส", "ตายเฉียบพลัน"
            )
        )

    def test_contains_value_false(self):
        data = {
            "animal_type": "หมู วัว ควาย",
            "swine_skin_symptoms__value": "แผลเรื้อรัง, แผลที่ปาก",
            "swine_general_symptoms__value": "ตายเฉียบพลัน",
        }

        form_data = FormData(data)
        self.assertFalse(
            form_data.fields_end_with("_symptoms__value").contains_value(
                "มีตุ่มน้ำใส/แผลที่ปาก", "ตายเฉียบพลัน"
            )
        )

    def test_count_contain_value(self):
        data = {"cat_nervous_symptoms__value": "เดินเซ/เดินปัด,กัด/ดุร้ายผิดปกติ"}
        form_data = FormData(data)
        self.assertTrue(
            form_data.fields_end_with("_symptoms__value").count_contains_value(
                "เดินเซ/เดินปัด",
                "กัด/ดุร้ายผิดปกติ",
                "กลืนน้ำลายลำบาก/น้ำลายฟูมปาก",
                "หวาดระแวง/ตกใจง่าย/ไวต่อสิ่งเร้า",
                "ดุร้ายผิดวิสัย",
                "หอนมีเสียงแหบ",
            )
            >= 2,
        )

        data = {"cat_nervous_symptoms__value": "ดุร้ายผิดวิสัย,กัด/ดุร้ายผิดปกติ"}
        form_data = FormData(data)
        self.assertTrue(
            form_data.fields_end_with("_symptoms__value").count_contains_value(
                "เดินเซ/เดินปัด",
                "กัด/ดุร้ายผิดปกติ",
                "กลืนน้ำลายลำบาก/น้ำลายฟูมปาก",
                "หวาดระแวง/ตกใจง่าย/ไวต่อสิ่งเร้า",
                "ดุร้ายผิดวิสัย",
                "หอนมีเสียงแหบ",
            )
            >= 2,
        )

        data = {"cat_nervous_symptoms__value": "ดุร้ายผิดวิสัย"}
        form_data = FormData(data)
        self.assertFalse(
            form_data.fields_end_with("_symptoms__value").count_contains_value(
                "เดินเซ/เดินปัด",
                "กัด/ดุร้ายผิดปกติ",
                "กลืนน้ำลายลำบาก/น้ำลายฟูมปาก",
                "หวาดระแวง/ตกใจง่าย/ไวต่อสิ่งเร้า",
                "ดุร้ายผิดวิสัย",
                "หอนมีเสียงแหบ",
            )
            >= 2,
        )

    def test_count_contain_value_in_simple_eval_1(self):
        data = {"cat_nervous_symptoms__value": "เดินเซ/เดินปัด,กัด/ดุร้ายผิดปกติ"}
        s = SimpleEval()
        form_data = FormData(data)
        s.names = {"form_data": form_data}
        self.assertTrue(
            s.eval(
                """form_data.fields_end_with("_symptoms__value").count_contains_value(
                "เดินเซ/เดินปัด",
                "กัด/ดุร้ายผิดปกติ",
                "กลืนน้ำลายลำบาก/น้ำลายฟูมปาก",
                "หวาดระแวง/ตกใจง่าย/ไวต่อสิ่งเร้า",
                "ดุร้ายผิดวิสัย",
                "หอนมีเสียงแหบ",
            ) >= 2 or form_data.fields_end_with("_symptoms__value").count_contains_value(
                "ซึม", 
                "ไม่กินอาหาร", 
                "หลบตามที่มืด" 
            ) == 3
        """
            )
        )

    def test_count_contain_value_in_simple_eval_2(self):
        data = {"cat_nervous_symptoms__value": ",ซึม,ไม่กินอาหาร,หลบตามที่มืด"}
        s = SimpleEval()
        form_data = FormData(data)
        s.names = {"form_data": form_data}
        self.assertTrue(
            s.eval(
                """form_data.fields_end_with("_symptoms__value").count_contains_value(
                "เดินเซ/เดินปัด",
                "กัด/ดุร้ายผิดปกติ",
                "กลืนน้ำลายลำบาก/น้ำลายฟูมปาก",
                "หวาดระแวง/ตกใจง่าย/ไวต่อสิ่งเร้า",
                "ดุร้ายผิดวิสัย",
                "หอนมีเสียงแหบ",
            ) >= 2 or form_data.fields_end_with("_symptoms__value").count_contains_value(
                "ซึม", 
                "ไม่กินอาหาร", 
                "หลบตามที่มืด" 
            ) == 3
        """
            )
        )
