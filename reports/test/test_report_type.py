from accounts.models import Authority
from reports.models import ReportType, Category
from django.test import TestCase


class ReportTypeTestCase(TestCase):
    def setUp(self):
        self.thailand = Authority.objects.create(code="TH", name="Thailand")
        self.bkk = Authority.objects.create(code="BKK", name="Bangkok")
        self.jatujak = Authority.objects.create(code="jatujak", name="jatujak")
        self.bkk.inherits.add(self.thailand)
        self.jatujak.inherits.add(self.bkk)

        self.cm = Authority.objects.create(code="CM", name="Chiangmai")
        self.cm.inherits.add(self.thailand)

        self.animal_category = Category.objects.create(name="animal")
        self.env_category = Category.objects.create(name="environment")

        self.animal_sick_death_report_type = ReportType.objects.create(
            name="Animal Sick/Death",
            category=self.animal_category,
            definition={},
        )
        self.animal_sick_death_report_type.authorities.add(self.thailand)

        self.wildfire_report_type = ReportType.objects.create(
            name="wildfire",
            category=self.env_category,
            definition={},
        )
        self.wildfire_report_type.authorities.add(self.cm)

    def test_bkk_must_see_animal_sick_death_report_type(self):
        report_types = ReportType.filter_by_authority(self.bkk)
        self.assertIn(self.animal_sick_death_report_type, report_types)

    def test_cm_must_see_animal_sick_death_report_type(self):
        report_types = ReportType.filter_by_authority(self.cm)
        self.assertIn(self.animal_sick_death_report_type, report_types)

    def test_bkk_should_not_see_wildfire_report_type(self):
        report_types = ReportType.filter_by_authority(self.bkk)
        self.assertNotIn(self.wildfire_report_type, report_types)
        self.assertEqual(1, len(report_types))

    def test_cm_must_see_wildfire_report_type(self):
        report_types = ReportType.filter_by_authority(self.cm)
        self.assertIn(self.wildfire_report_type, report_types)
        self.assertEqual(2, len(report_types))
