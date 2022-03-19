from reports.models import ReportType
from reports.test.base_testcase import BaseTestCase


class ReportTypeTestCase(BaseTestCase):
    def setUp(self):
        super(ReportTypeTestCase, self).setUp()

    def test_bkk_must_see_animal_sick_death_report_type(self):
        report_types = ReportType.filter_by_authority(self.bkk)
        self.assertIn(self.animal_sick_death_report_type, report_types)

    def test_cm_must_see_animal_sick_death_report_type(self):
        report_types = ReportType.filter_by_authority(self.cm)
        self.assertIn(self.animal_sick_death_report_type, report_types)

    def test_bkk_should_not_see_wildfire_report_type(self):
        report_types = ReportType.filter_by_authority(self.bkk)
        self.assertNotIn(self.wildfire_report_type, report_types)
        self.assertEqual(3, len(report_types))

    def test_cm_must_see_wildfire_report_type(self):
        report_types = ReportType.filter_by_authority(self.cm)
        self.assertIn(self.wildfire_report_type, report_types)
        self.assertEqual(4, len(report_types))

    def test_render_data_template(self):
        rt = ReportType()
        rt.renderer_data_template = "-{{ name }}-"
        renderer_text = rt.render_data({"name": "test"})
        self.assertEqual("-test-", renderer_text)

    def test_null_render_data_template(self):
        rt = ReportType()
        renderer_text = rt.render_data({"name": "test"})
        self.assertEqual("", renderer_text)
