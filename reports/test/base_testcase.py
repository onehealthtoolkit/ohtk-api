from django.test import TestCase

from accounts.models import Authority
from reports.models import Category, ReportType


class BaseTestCase(TestCase):
    def setUp(self):
        """
                            ┌──────────┐    ┌──────────┐   ┌──────────┐
                            │ thailand │◀┬──│   bkk    │◀──│ jatujak  │
                            └──────────┘ │  └──────────┘   └──────────┘
                                  ▲      │  ┌──────────┐
              ┌─────────┬─────────┴───┐  └──│    cm    │
              │         │             │     └──────────┘
        ╔══════════╗ ╔═════╗ ╔═════════════════╗  ▲        ╔══════════╗
        ║  dengue  ║ ║mers ║ ║animal sick/death║  └────────║ wildfire ║
        ╚══════════╝ ╚═════╝ ╚═════════════════╝           ╚══════════╝
        """
        self.thailand = Authority.objects.create(code="TH", name="Thailand")

        self.bkk = Authority.objects.create(code="BKK", name="Bangkok")
        self.jatujak = Authority.objects.create(code="jatujak", name="jatujak")
        self.bkk.inherits.add(self.thailand)
        self.jatujak.inherits.add(self.bkk)

        self.cm = Authority.objects.create(code="CM", name="Chiangmai")
        self.cm.inherits.add(self.thailand)

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

        self.animal_category = Category.objects.create(name="animal")
        self.animal_sick_death_report_type = ReportType.objects.create(
            name="Animal Sick/Death",
            category=self.animal_category,
            definition={},
        )
        self.animal_sick_death_report_type.authorities.add(self.thailand)

        self.env_category = Category.objects.create(name="environment")
        self.wildfire_report_type = ReportType.objects.create(
            name="wildfire",
            category=self.env_category,
            definition={},
        )
        self.wildfire_report_type.authorities.add(self.cm)

        self.thailand_reports = [
            self.mers_report_type.to_data(),
            self.dengue_report_type.to_data(),
            self.animal_sick_death_report_type.to_data(),
        ]

        self.cm_reports = [
            self.mers_report_type.to_data(),
            self.dengue_report_type.to_data(),
            self.animal_sick_death_report_type.to_data(),
            self.wildfire_report_type.to_data(),
        ]
