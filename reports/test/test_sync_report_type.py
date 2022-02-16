from accounts.models import Authority
from reports.models import ReportType, Category
from django.test import TestCase


class SyncReportTypeTestCase(TestCase):
    def setUp(self):
        self.thailand = Authority.objects.create(code="TH", name="Thailand")
        self.human_category = Category.objects.create(name="human")
        self.dengue_report_type = ReportType.objects.create(
            name="Dengue",
            category=self.human_category,
            definition={},
        )
        self.dengue_report_type.authorities.add(self.thailand)
        self.mers_report_type = ReportType.objects.create(
            name="Mers",
            category=self.human_category,
            definition={},
        )
        self.mers_report_type.authorities.add(self.thailand)
        self.snapshot = list(map(lambda item: item.to_data(), ReportType.objects.all()))

    def test_no_change_found(self):
        result = ReportType.check_updated_report_types_by_authority(
            self.thailand,
            self.snapshot,
        )
        self.assertEqual(0, len(result["updated_list"]))
        self.assertEqual(0, len(result["removed_list"]))

    def test_something_changed(self):
        self.mers_report_type.definition = {"changeme": True}
        self.mers_report_type.save()

        result = ReportType.check_updated_report_types_by_authority(
            self.thailand,
            self.snapshot,
        )
        self.assertEqual(1, len(result["updated_list"]))
        self.assertEqual(0, len(result["removed_list"]))
        self.assertIn(self.mers_report_type, result["updated_list"])

    def test_something_has_removed(self):
        self.mers_report_type.authorities.clear()
        result = ReportType.check_updated_report_types_by_authority(
            self.thailand,
            self.snapshot,
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
            self.snapshot,
        )
        self.assertEqual(1, len(result["updated_list"]))
        self.assertEqual(0, len(result["removed_list"]))
        self.assertIn(flu_type, result["updated_list"])
