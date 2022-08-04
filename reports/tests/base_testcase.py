from django.test import TestCase

from accounts.models import Authority, AuthorityUser
from reports.models import Category, ReportType

bkk_area = """
      {
        "type": "Polygon",
        "coordinates": [
          [
            [
              100.43701171875,
              13.870080100685891
            ],
            [
              100.4644775390625,
              13.747388924343081
            ],
            [
              100.6292724609375,
              13.75806028283862
            ],
            [
              100.6842041015625,
              13.902075852500495
            ],
            [
              100.535888671875,
              13.987376214146467
            ],
            [
              100.43701171875,
              13.870080100685891
            ]
          ]
        ]
      }"""

cm_area = """
      {
        "type": "Polygon",
        "coordinates": [
          [
            [
              98.624267578125,
              19.062117883514652
            ],
            [
              98.624267578125,
              18.58377568837094
            ],
            [
              98.94287109375,
              18.3336694457713
            ],
            [
              99.38232421875,
              18.656654486540006
            ],
            [
              99.31640625,
              19.02057711096681
            ],
            [
              98.800048828125,
              19.37334071336406
            ],
            [
              98.624267578125,
              19.062117883514652
            ]
          ]
        ]
      }
"""


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

        self.bkk = Authority.objects.create(code="BKK", name="Bangkok", area=bkk_area)
        self.jatujak = Authority.objects.create(
            code="jatujak",
            name="jatujak",
        )
        self.bkk.inherits.add(self.thailand)
        self.jatujak.inherits.add(self.bkk)

        self.cm = Authority.objects.create(code="CM", name="Chiangmai", area=cm_area)
        self.cm.inherits.add(self.thailand)

        self.human_category = Category.objects.create(name="human")
        self.dengue_report_type = ReportType.objects.create(
            name="Dengue",
            category=self.human_category,
            definition={},
            renderer_data_template="{{name}}",
        )
        self.dengue_report_type.authorities.add(self.thailand)
        self.mers_report_type = ReportType.objects.create(
            name="Mers",
            category=self.human_category,
            definition={},
            renderer_data_template="number of sick {{ data.number_of_sick }} with symptom {{ data.symptom }}",
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

        self.user = AuthorityUser.objects.create(
            username="test", authority=self.thailand
        )

        self.jatujak_reporter = AuthorityUser.objects.create(
            username="reporter", authority=self.jatujak
        )
