from django.utils import timezone
from graphql_jwt.testcases import JSONWebTokenTestCase

from accounts.models import Authority, AuthorityUser, Village, VillageReporterAssignment
from accounts.village_capability import set_village_capability_enabled
from census.animal_census_capability import set_animal_census_capability_enabled
from census.census_definition_defaults import (
    DEFAULT_ANIMAL_DEFINITION_SCHEMA,
    default_schema_for_kind,
)
from census.definition_schema import (
    generate_runtime_schema,
    is_grouped_animal_schema,
    validate_definition_schema,
)
from census.models import (
    AnimalCensusFact,
    CensusDefinition,
    CensusDefinitionVersion,
    CensusRoundDefinition,
)
from census.rounds import materialize_occurrence, species_summary


class GroupedAnimalCensusSchemaTests(JSONWebTokenTestCase):
    def setUp(self):
        self.authority = Authority.objects.create(name="Authority 1", code="A1")
        self.village = Village.objects.create(
            name="Village 1", code="V1", authority=self.authority
        )
        self.reporter = AuthorityUser.objects.create(
            username="official1",
            authority=self.authority,
            role=AuthorityUser.Role.REPORTER,
        )
        VillageReporterAssignment.objects.create(
            reporter=self.reporter,
            village=self.village,
            census_role=VillageReporterAssignment.CensusRole.OFFICIAL,
        )
        set_village_capability_enabled(True)
        set_animal_census_capability_enabled(True)
        self.client.authenticate(self.reporter)

    def test_default_animal_schema_is_grouped_option_a(self):
        self.assertTrue(is_grouped_animal_schema(DEFAULT_ANIMAL_DEFINITION_SCHEMA))
        self.assertEqual(validate_definition_schema(DEFAULT_ANIMAL_DEFINITION_SCHEMA), [])
        runtime = default_schema_for_kind(CensusDefinition.Kind.ANIMAL)
        self.assertEqual(runtime["layout"], "grouped_species")
        self.assertEqual(runtime["schema_version"], 2)

        row_keys = [row["row_key"] for row in runtime["rows"]]
        self.assertIn("group:PIG", row_keys)
        self.assertIn("species:PIG", row_keys)
        self.assertIn("group:LARGE_RUMINANT", row_keys)
        self.assertIn("species:CATTLE", row_keys)

        by_key = {row["row_key"]: row for row in runtime["rows"]}
        pig_group_measures = {m["key"] for m in by_key["group:PIG"]["measures"]}
        pig_species_measures = {m["key"] for m in by_key["species:PIG"]["measures"]}
        self.assertEqual(pig_group_measures, {"household_quantity"})
        self.assertEqual(pig_species_measures, {"animal_quantity"})

    def test_flat_v1_schema_still_generates(self):
        authored = {
            "schema_version": 1,
            "dimensions": [
                {
                    "key": "species",
                    "label": {"default": "Species"},
                    "values": [
                        {"key": "CATTLE", "label": {"default": "Cattle"}},
                    ],
                }
            ],
            "measures": [
                {
                    "key": "animal_quantity",
                    "label": {"default": "Heads"},
                    "type": "integer",
                    "required": True,
                },
                {
                    "key": "household_quantity",
                    "label": {"default": "HH"},
                    "type": "integer",
                    "required": True,
                },
            ],
        }
        runtime = generate_runtime_schema(authored)
        self.assertEqual(runtime["layout"], "flat")
        self.assertEqual(len(runtime["rows"]), 1)

    def _publish_grouped_definition(self):
        definition = CensusDefinition.objects.create(
            kind=CensusDefinition.Kind.ANIMAL, enabled=True, sort_order=1
        )
        authored = DEFAULT_ANIMAL_DEFINITION_SCHEMA
        version = CensusDefinitionVersion.objects.create(
            definition=definition,
            version=1,
            status=CensusDefinitionVersion.Status.PUBLISHED,
            schema=generate_runtime_schema(authored),
            definition_schema=authored,
            published_at=timezone.now(),
        )
        round_def = CensusRoundDefinition.objects.create(
            code="ANIMAL_Y",
            name="Animal year",
            kind=CensusDefinition.Kind.ANIMAL,
            mode=CensusRoundDefinition.Mode.PRODUCTION,
            census_period_start="01-01",
            census_period_end="12-31",
            start_date="01-01",
            soft_finish_date="11-30",
            hard_finish_date="12-31",
            enabled=True,
        )
        occurrence = materialize_occurrence(round_def, 2026)
        return definition, version, occurrence

    def _grouped_form_data(self, **overrides):
        rows = [
            {
                "row_key": "group:LARGE_RUMINANT",
                "measures": {"household_quantity": 10},
            },
            {"row_key": "species:CATTLE", "measures": {"animal_quantity": 20}},
            {"row_key": "species:BUFFALO", "measures": {"animal_quantity": 5}},
            {"row_key": "group:PIG", "measures": {"household_quantity": 8}},
            {"row_key": "species:PIG", "measures": {"animal_quantity": 40}},
            {
                "row_key": "group:SMALL_RUMINANT",
                "measures": {"household_quantity": 3},
            },
            {"row_key": "species:SHEEP", "measures": {"animal_quantity": 4}},
            {"row_key": "species:GOAT", "measures": {"animal_quantity": 6}},
            {"row_key": "group:POULTRY", "measures": {"household_quantity": 15}},
            {"row_key": "species:CHICKEN", "measures": {"animal_quantity": 100}},
            {
                "row_key": "species:OTHER_POULTRY",
                "measures": {"animal_quantity": 20},
            },
        ]
        form_data = {
            "summary": {
                "village_household_quantity": 50,
                "animal_household_quantity": 30,
            },
            "rows": rows,
        }
        form_data.update(overrides)
        return form_data

    def test_submit_grouped_form_stores_group_and_species_facts(self):
        _, version, occurrence = self._publish_grouped_definition()
        mutation = """
            mutation submit(
              $villageId: Int!
              $definitionVersionId: Int!
              $occurrenceId: Int
              $censusDate: Date!
              $formData: GenericScalar!
            ) {
              submitVillageCensusSnapshotV2(
                villageId: $villageId
                definitionVersionId: $definitionVersionId
                occurrenceId: $occurrenceId
                censusDate: $censusDate
                formData: $formData
              ) {
                result {
                  ... on VillageCensusSnapshotType {
                    id
                  }
                  ... on VillageCensusSnapshotProblem {
                    fields { name message }
                  }
                }
              }
            }
        """
        result = self.client.execute(
            mutation,
            variables={
                "villageId": self.village.id,
                "definitionVersionId": version.id,
                "occurrenceId": occurrence.id,
                "censusDate": "2026-07-01",
                "formData": self._grouped_form_data(),
            },
        )
        self.assertIsNone(result.errors, result.errors)
        payload = result.data["submitVillageCensusSnapshotV2"]["result"]
        self.assertNotIn("fields", payload, payload)

        facts = {
            f.row_key: f.measures
            for f in AnimalCensusFact.objects.filter(snapshot_id=payload["id"])
        }
        self.assertEqual(facts["group:PIG"], {"household_quantity": 8})
        self.assertEqual(facts["species:PIG"], {"animal_quantity": 40})
        self.assertEqual(facts["group:LARGE_RUMINANT"], {"household_quantity": 10})
        self.assertNotIn("household_quantity", facts["species:CATTLE"])
        self.assertEqual(facts["species:CATTLE"]["animal_quantity"], 20)

        snapshot = AnimalCensusFact.objects.filter(snapshot_id=payload["id"]).first().snapshot
        summary = species_summary(snapshot)
        summary_keys = {row["row_key"] for row in summary}
        self.assertNotIn("group:PIG", summary_keys)
        self.assertIn("species:PIG", summary_keys)

    def test_submit_rejects_heads_without_group_households(self):
        _, version, occurrence = self._publish_grouped_definition()
        form_data = self._grouped_form_data()
        for row in form_data["rows"]:
            if row["row_key"] == "group:PIG":
                row["measures"] = {"household_quantity": 0}

        mutation = """
            mutation submit(
              $villageId: Int!
              $definitionVersionId: Int!
              $occurrenceId: Int
              $censusDate: Date!
              $formData: GenericScalar!
            ) {
              submitVillageCensusSnapshotV2(
                villageId: $villageId
                definitionVersionId: $definitionVersionId
                occurrenceId: $occurrenceId
                censusDate: $censusDate
                formData: $formData
              ) {
                result {
                  ... on VillageCensusSnapshotProblem {
                    fields { name message }
                  }
                }
              }
            }
        """
        result = self.client.execute(
            mutation,
            variables={
                "villageId": self.village.id,
                "definitionVersionId": version.id,
                "occurrenceId": occurrence.id,
                "censusDate": "2026-07-01",
                "formData": form_data,
            },
        )
        self.assertIsNone(result.errors, result.errors)
        fields = result.data["submitVillageCensusSnapshotV2"]["result"]["fields"]
        messages = [f["message"] for f in fields]
        self.assertTrue(
            any("group households must be at least 1" in m for m in messages)
            or any("must be zero when households is zero" in m for m in messages),
            messages,
        )
