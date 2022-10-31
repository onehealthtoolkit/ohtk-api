from reports.models import ReportType

from reports.tests.base_testcase import BaseTestCase


class SyncReportTypeTestCase(BaseTestCase):
    def setUp(self):
        super(SyncReportTypeTestCase, self).setUp()

    def test_no_change_found(self):
        result = ReportType.check_updated_report_types_by_authority(
            self.thailand,
            self.thailand_reports,
        )
        self.assertEqual(0, len(result["updated_list"]))
        self.assertEqual(0, len(result["removed_list"]))

    def test_something_changed(self):
        self.mers_report_type.definition = {"changeme": True}
        self.mers_report_type.save()

        result = ReportType.check_updated_report_types_by_authority(
            self.thailand,
            self.thailand_reports,
        )
        self.assertEqual(1, len(result["updated_list"]))
        self.assertEqual(0, len(result["removed_list"]))
        self.assertIn(self.mers_report_type, result["updated_list"])

    def test_something_has_removed(self):
        self.mers_report_type.delete()
        result = ReportType.check_updated_report_types_by_authority(
            self.thailand,
            self.thailand_reports,
        )
        self.assertEqual(0, len(result["updated_list"]))
        self.assertEqual(1, len(result["removed_list"]))

    def test_new_report_type_has_beed_added(self):
        flu_type = ReportType.objects.create(
            name="Flu",
            category=self.human_category,
            definition={},
        )
        flu_type.authorities.add(self.thailand)
        result = ReportType.check_updated_report_types_by_authority(
            self.thailand,
            self.thailand_reports,
        )
        self.assertEqual(1, len(result["updated_list"]))
        self.assertEqual(0, len(result["removed_list"]))
        self.assertIn(flu_type, result["updated_list"])
