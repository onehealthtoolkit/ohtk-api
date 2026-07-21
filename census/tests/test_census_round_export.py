from django.test import RequestFactory, TestCase

from accounts.models import Authority, AuthorityUser, Village
from accounts.village_capability import set_village_capability_enabled
from census.animal_census_capability import set_animal_census_capability_enabled
from census.export import authority_hierarchy_path, build_export_table
from census.models import (
    CensusDefinition,
    CensusDefinitionVersion,
    CensusRoundDefinition,
    VillageCensusSnapshot,
)
from census.rounds import materialize_occurrence
from census.views import export_census_round_xls


class CensusRoundExportTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.root = Authority.objects.create(name="Province", code="P1")
        self.district = Authority.objects.create(name="District", code="D1")
        self.district.inherits.add(self.root)
        self.village = Village.objects.create(
            code="V001", name="Village One", authority=self.district
        )
        self.other_authority = Authority.objects.create(name="Other", code="OX")
        self.outside = Village.objects.create(
            code="V999", name="Outside", authority=self.other_authority
        )
        self.officer = AuthorityUser.objects.create(
            username="export-officer",
            authority=self.root,
            role=AuthorityUser.Role.OFFICER,
        )
        set_village_capability_enabled(True)
        set_animal_census_capability_enabled(True)
        definition = CensusDefinition.objects.create(
            kind=CensusDefinition.Kind.ANIMAL, enabled=True, sort_order=1
        )
        self.version = CensusDefinitionVersion.objects.create(
            definition=definition,
            version=1,
            status=CensusDefinitionVersion.Status.PUBLISHED,
            schema={
                "rows": [
                    {
                        "key": "species:CATTLE",
                        "row_key": "species:CATTLE",
                        "label": "Cattle",
                    }
                ],
                "measures": [
                    {"key": "animal_quantity", "label": "Animals", "type": "integer"}
                ],
            },
        )
        round_definition = CensusRoundDefinition.objects.create(
            code="ANIMAL_H1",
            name="H1",
            kind=CensusDefinition.Kind.ANIMAL,
            mode=CensusRoundDefinition.Mode.PRODUCTION,
            census_period_start="01-01",
            census_period_end="06-30",
            start_date="05-01",
            soft_finish_date="05-20",
            hard_finish_date="05-31",
            enabled=True,
        )
        self.occurrence = materialize_occurrence(round_definition, 2026)
        snapshot = VillageCensusSnapshot.objects.create(
            village=self.village,
            reporter=self.officer,
            definition_version=self.version,
            round_occurrence=self.occurrence,
            census_date="2026-05-10",
            form_data={
                "summary": {
                    "village_household_quantity": 10,
                    "animal_household_quantity": 4,
                }
            },
        )
        from census.models import AnimalCensusFact

        AnimalCensusFact.objects.create(
            snapshot=snapshot,
            row_key="species:CATTLE",
            row_label="Cattle",
            extra_dimensions={"species": "CATTLE"},
            measures={"animal_quantity": 12},
        )

    def test_authority_hierarchy_path_root_to_leaf(self):
        path = authority_hierarchy_path(self.district)
        self.assertEqual([item.code for item in path], ["P1", "D1"])

    def test_build_export_table_hierarchy_and_species_columns(self):
        table = build_export_table(self.occurrence, self.officer)
        self.assertIsNotNone(table)
        self.assertIn("Authority L1", table["headers"])
        self.assertIn("Authority L2", table["headers"])
        self.assertIn("Cattle", table["headers"])
        self.assertIn("Total animals", table["headers"])

        # Outside hierarchy village must not appear.
        codes = [row[table["headers"].index("Village code")] for row in table["rows"]]
        self.assertEqual(codes, ["V001"])
        self.assertNotIn("V999", codes)

        row = table["rows"][0]
        self.assertEqual(row[table["headers"].index("Authority L1")], "Province")
        self.assertEqual(row[table["headers"].index("Authority L2")], "District")
        self.assertEqual(row[table["headers"].index("Cattle")], 12)
        self.assertEqual(row[table["headers"].index("Total animals")], 12)
        self.assertEqual(row[table["headers"].index("Village households")], 10)

    def test_export_view_requires_auth_and_returns_xls(self):
        request = self.factory.get(
            "/excels/census_round",
            {"occurrenceId": self.occurrence.id},
        )
        request.user = self.officer
        response = export_census_round_xls(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/ms-excel")
        self.assertIn("census_round_", response["Content-Disposition"])
        self.assertTrue(len(response.content) > 0)

    def test_export_view_rejects_anonymous(self):
        from django.contrib.auth.models import AnonymousUser

        request = self.factory.get(
            "/excels/census_round",
            {"occurrenceId": self.occurrence.id},
        )
        request.user = AnonymousUser()
        response = export_census_round_xls(request)
        self.assertEqual(response.status_code, 401)
