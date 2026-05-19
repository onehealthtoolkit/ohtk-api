from datetime import date

from django.utils import timezone
from django.db import IntegrityError, transaction
from graphql_jwt.testcases import JSONWebTokenTestCase

from accounts.animal_census_capability import set_animal_census_capability_enabled
from accounts.models import (
    AnimalCensusFact,
    AnimalSpecies,
    Authority,
    AuthorityUser,
    CensusDefinition,
    CensusDefinitionVersion,
    CurrentAnimalCensusFact,
    CurrentHumanCensusFact,
    HumanCensusFact,
    Village,
    VillageCensusSnapshot,
    VillageReporterAssignment,
)
from accounts.village_capability import set_village_capability_enabled


class DynamicCensusDefinitionBackendTests(JSONWebTokenTestCase):
    def setUp(self):
        self.authority = Authority.objects.create(name="test authority", code="TA")
        self.village = Village.objects.create(
            code="V001", name="Village One", authority=self.authority
        )
        self.reporter = AuthorityUser.objects.create(
            username="official-reporter",
            authority=self.authority,
            role=AuthorityUser.Role.REPORTER,
        )
        VillageReporterAssignment.objects.create(
            reporter=self.reporter,
            village=self.village,
            census_role=VillageReporterAssignment.CensusRole.OFFICIAL,
        )

    def enable_census(self):
        set_village_capability_enabled(True)
        set_animal_census_capability_enabled(True)

    def create_species(self):
        cattle = AnimalSpecies.objects.create(
            code="CATTLE", name="Cattle", sort_order=1
        )
        buffalo = AnimalSpecies.objects.create(
            code="BUFFALO", name="Buffalo", sort_order=2
        )
        return cattle, buffalo

    def create_animal_definition(self):
        definition = CensusDefinition.objects.create(
            kind=CensusDefinition.Kind.ANIMAL,
            enabled=True,
            sort_order=1,
        )
        version = CensusDefinitionVersion.objects.create(
            definition=definition,
            version=1,
            status=CensusDefinitionVersion.Status.PUBLISHED,
            schema={
                "row_source": "ACTIVE_ANIMAL_SPECIES",
                "measures": [
                    {
                        "key": "animal_quantity",
                        "label": "Animal quantity",
                        "type": "integer",
                        "required": True,
                    },
                    {
                        "key": "household_quantity",
                        "label": "Households",
                        "type": "integer",
                        "required": True,
                    },
                ],
                "extra_dimensions": [],
            },
            published_at=timezone.now(),
        )
        return definition, version

    def create_human_definition(self):
        definition = CensusDefinition.objects.create(
            kind=CensusDefinition.Kind.HUMAN,
            enabled=True,
            sort_order=2,
        )
        version = CensusDefinitionVersion.objects.create(
            definition=definition,
            version=1,
            status=CensusDefinitionVersion.Status.PUBLISHED,
            schema={
                "rows": [
                    {
                        "key": "male",
                        "label": "Male",
                        "dimensions": {"gender": "male"},
                    },
                    {
                        "key": "female",
                        "label": "Female",
                        "dimensions": {"gender": "female"},
                    },
                ],
                "measures": [
                    {
                        "key": "population",
                        "label": "Population",
                        "type": "integer",
                        "required": True,
                    }
                ],
            },
            published_at=timezone.now(),
        )
        return definition, version

    def animal_form_data(self, cattle, buffalo):
        return {
            "rows": [
                {
                    "species_id": cattle.id,
                    "measures": {
                        "animal_quantity": 10,
                        "household_quantity": 4,
                    },
                },
                {
                    "species_id": buffalo.id,
                    "measures": {
                        "animal_quantity": 2,
                        "household_quantity": 1,
                    },
                },
            ]
        }

    def human_form_data(self):
        return {
            "rows": [
                {"row_key": "male", "measures": {"population": 20}},
                {"row_key": "female", "measures": {"population": 25}},
            ]
        }

    def execute_submit_v2(self, variables):
        mutation = """
        mutation submitVillageCensusSnapshotV2(
            $villageId: Int!,
            $definitionVersionId: Int!,
            $censusDate: Date!,
            $formData: GenericScalar!
        ) {
            submitVillageCensusSnapshotV2(
                villageId: $villageId,
                definitionVersionId: $definitionVersionId,
                censusDate: $censusDate,
                formData: $formData
            ) {
                result {
                    __typename
                    ... on VillageCensusSnapshotType {
                        id
                        censusDate
                        status
                        formData
                        definitionVersion {
                            version
                            definition {
                                kind
                            }
                        }
                        facts {
                            rowKey
                            animalSpecies {
                                code
                            }
                            species {
                                code
                            }
                            extraDimensions
                            measures
                            animalQuantity
                            householdQuantity
                        }
                        humanFacts {
                            rowKey
                            dimensions
                            measures
                        }
                    }
                    ... on VillageCensusSnapshotProblem {
                        fields {
                            name
                            message
                        }
                    }
                }
            }
        }
        """
        return self.client.execute(mutation, variables)

    def execute_active_kind_summary(self):
        query = """
        query activeVillageCensusDefinitions($villageId: Int!) {
            activeVillageCensusDefinitions(villageId: $villageId) {
                kind
                name
                enabled
                activeVersion {
                    id
                    version
                    status
                    definition {
                        kind
                    }
                }
                latestSnapshot {
                    id
                    censusDate
                    definitionVersion {
                        definition {
                            kind
                        }
                    }
                }
            }
        }
        """
        return self.client.execute(query, {"villageId": self.village.id})

    def test_reporter_can_query_runtime_animal_census_schema(self):
        self.enable_census()
        cattle, _buffalo = self.create_species()
        self.create_animal_definition()
        self.client.authenticate(self.reporter)
        query = """
        query activeCensusDefinitionVersion($kind: String!) {
            activeCensusDefinitionVersion(kind: $kind) {
                version
                definition {
                    kind
                    enabled
                }
                schema
                runtimeSchema
            }
            censusDefinitions {
                kind
                enabled
            }
        }
        """

        result = self.client.execute(query, {"kind": "ANIMAL"})

        self.assertIsNone(result.errors, result.errors)
        version = result.data["activeCensusDefinitionVersion"]
        self.assertEqual(version["definition"]["kind"], "ANIMAL")
        self.assertEqual(version["schema"]["row_source"], "ACTIVE_ANIMAL_SPECIES")
        self.assertEqual(version["runtimeSchema"]["rows"][0]["species_id"], cattle.id)
        self.assertEqual(result.data["censusDefinitions"][0]["kind"], "ANIMAL")

    def test_reporter_can_query_active_animal_kind_summary(self):
        self.enable_census()
        self.create_animal_definition()
        self.client.authenticate(self.reporter)

        result = self.execute_active_kind_summary()

        self.assertIsNone(result.errors, result.errors)
        summaries = result.data["activeVillageCensusDefinitions"]
        self.assertEqual(len(summaries), 1)
        self.assertEqual(summaries[0]["kind"], "ANIMAL")
        self.assertEqual(summaries[0]["name"], "Animal census")
        self.assertTrue(summaries[0]["enabled"])
        self.assertEqual(summaries[0]["activeVersion"]["version"], 1)
        self.assertIsNone(summaries[0]["latestSnapshot"])

    def test_reporter_can_query_active_human_kind_summary(self):
        self.enable_census()
        self.create_human_definition()
        self.client.authenticate(self.reporter)

        result = self.execute_active_kind_summary()

        self.assertIsNone(result.errors, result.errors)
        summaries = result.data["activeVillageCensusDefinitions"]
        self.assertEqual(len(summaries), 1)
        self.assertEqual(summaries[0]["kind"], "HUMAN")
        self.assertEqual(summaries[0]["name"], "Human census")
        self.assertEqual(summaries[0]["activeVersion"]["definition"]["kind"], "HUMAN")

    def test_reporter_can_query_multiple_kind_summaries_with_latest_snapshot(self):
        self.enable_census()
        self.create_animal_definition()
        _definition, human_version = self.create_human_definition()
        VillageCensusSnapshot.objects.create(
            village=self.village,
            reporter=self.reporter,
            definition_version=human_version,
            census_date=date(2026, 5, 19),
        )
        self.client.authenticate(self.reporter)

        result = self.execute_active_kind_summary()

        self.assertIsNone(result.errors, result.errors)
        summaries = result.data["activeVillageCensusDefinitions"]
        self.assertEqual([summary["kind"] for summary in summaries], ["ANIMAL", "HUMAN"])
        human = summaries[1]
        self.assertEqual(human["latestSnapshot"]["censusDate"], "2026-05-19")
        self.assertEqual(
            human["latestSnapshot"]["definitionVersion"]["definition"]["kind"],
            "HUMAN",
        )

    def test_active_kind_summary_returns_empty_when_no_kind_is_configured(self):
        self.enable_census()
        self.client.authenticate(self.reporter)

        result = self.execute_active_kind_summary()

        self.assertIsNone(result.errors, result.errors)
        self.assertEqual(result.data["activeVillageCensusDefinitions"], [])

    def test_active_kind_summary_returns_empty_when_census_feature_is_disabled(self):
        self.create_animal_definition()
        self.client.authenticate(self.reporter)

        result = self.execute_active_kind_summary()

        self.assertIsNone(result.errors, result.errors)
        self.assertEqual(result.data["activeVillageCensusDefinitions"], [])

    def test_admin_can_ensure_default_definitions_and_species(self):
        super_user = AuthorityUser.objects.create(
            username="platform-admin",
            authority=self.authority,
            role=AuthorityUser.Role.ADMIN,
            is_superuser=True,
        )
        self.client.authenticate(super_user)
        mutation = """
        mutation ensureDefaults {
            adminCensusDefinitionsEnsureDefaults {
                definitions {
                    kind
                    enabled
                }
                versions {
                    version
                    definition {
                        kind
                    }
                    schema
                    runtimeSchema
                }
                fields {
                    name
                    message
                }
            }
        }
        """

        result = self.client.execute(mutation)

        self.assertIsNone(result.errors, result.errors)
        payload = result.data["adminCensusDefinitionsEnsureDefaults"]
        self.assertEqual(
            {definition["kind"] for definition in payload["definitions"]},
            {"ANIMAL", "HUMAN"},
        )
        animal_version = next(
            version
            for version in payload["versions"]
            if version["definition"]["kind"] == "ANIMAL"
        )
        self.assertEqual(
            animal_version["schema"]["row_source"], "ACTIVE_ANIMAL_SPECIES"
        )
        self.assertEqual(animal_version["runtimeSchema"]["rows"][0]["species_code"], "CATTLE")
        self.assertTrue(AnimalSpecies.objects.filter(code="POULTRY").exists())

    def test_admin_can_publish_new_human_schema_version(self):
        super_user = AuthorityUser.objects.create(
            username="schema-admin",
            authority=self.authority,
            role=AuthorityUser.Role.ADMIN,
            is_superuser=True,
        )
        self.client.authenticate(super_user)
        mutation = """
        mutation publishHumanSchema($schema: GenericScalar!) {
            adminCensusDefinitionVersionPublish(kind: "HUMAN", schema: $schema) {
                definition {
                    kind
                    enabled
                }
                version {
                    version
                    status
                    schema
                }
                fields {
                    name
                    message
                }
            }
        }
        """
        schema = {
            "rows": [
                {
                    "key": "adult",
                    "label": "Adult",
                    "dimensions": {"age_group": "adult"},
                }
            ],
            "measures": [
                {
                    "key": "population",
                    "label": "Population",
                    "type": "integer",
                    "required": True,
                }
            ],
        }

        result = self.client.execute(mutation, {"schema": schema})

        self.assertIsNone(result.errors, result.errors)
        payload = result.data["adminCensusDefinitionVersionPublish"]
        self.assertEqual(payload["definition"]["kind"], "HUMAN")
        self.assertEqual(payload["version"]["version"], 1)
        self.assertEqual(payload["version"]["schema"]["rows"][0]["key"], "adult")

    def test_census_definition_kind_is_unique(self):
        CensusDefinition.objects.create(kind=CensusDefinition.Kind.ANIMAL)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CensusDefinition.objects.create(kind=CensusDefinition.Kind.ANIMAL)

    def test_official_reporter_can_submit_animal_snapshot_and_current_fact_pointers(self):
        self.enable_census()
        cattle, buffalo = self.create_species()
        _definition, version = self.create_animal_definition()
        self.client.authenticate(self.reporter)

        result = self.execute_submit_v2(
            {
                "villageId": self.village.id,
                "definitionVersionId": version.id,
                "censusDate": "2026-05-19",
                "formData": self.animal_form_data(cattle, buffalo),
            }
        )

        self.assertIsNone(result.errors, result.errors)
        snapshot = result.data["submitVillageCensusSnapshotV2"]["result"]
        self.assertEqual(snapshot["__typename"], "VillageCensusSnapshotType")
        self.assertEqual(snapshot["definitionVersion"]["definition"]["kind"], "ANIMAL")
        self.assertEqual(snapshot["formData"]["rows"][0]["species_id"], cattle.id)
        self.assertEqual(len(snapshot["facts"]), 2)
        self.assertEqual(snapshot["facts"][0]["animalSpecies"]["code"], "CATTLE")
        self.assertEqual(snapshot["facts"][0]["species"]["code"], "CATTLE")
        self.assertEqual(snapshot["facts"][0]["animalQuantity"], 10)
        self.assertTrue(
            AnimalCensusFact.objects.filter(
                animal_species=cattle,
                row_key="species:CATTLE",
                extra_dimensions={},
                measures={"animal_quantity": 10, "household_quantity": 4},
            ).exists()
        )
        self.assertEqual(CurrentAnimalCensusFact.objects.count(), 2)

    def test_official_reporter_can_submit_human_snapshot_and_current_fact_pointers(self):
        self.enable_census()
        _definition, version = self.create_human_definition()
        self.client.authenticate(self.reporter)

        result = self.execute_submit_v2(
            {
                "villageId": self.village.id,
                "definitionVersionId": version.id,
                "censusDate": "2026-05-19",
                "formData": self.human_form_data(),
            }
        )

        self.assertIsNone(result.errors, result.errors)
        snapshot = result.data["submitVillageCensusSnapshotV2"]["result"]
        self.assertEqual(snapshot["definitionVersion"]["definition"]["kind"], "HUMAN")
        self.assertEqual(len(snapshot["humanFacts"]), 2)
        male_fact = next(
            fact for fact in snapshot["humanFacts"] if fact["rowKey"] == "male"
        )
        self.assertEqual(male_fact["dimensions"], {"gender": "male"})
        self.assertTrue(
            HumanCensusFact.objects.filter(
                row_key="male",
                dimensions={"gender": "male"},
                measures={"population": 20},
            ).exists()
        )
        self.assertEqual(CurrentHumanCensusFact.objects.count(), 2)

    def test_submit_v2_rejects_missing_required_measure(self):
        self.enable_census()
        cattle, buffalo = self.create_species()
        _definition, version = self.create_animal_definition()
        self.client.authenticate(self.reporter)
        form_data = self.animal_form_data(cattle, buffalo)
        del form_data["rows"][0]["measures"]["household_quantity"]

        result = self.execute_submit_v2(
            {
                "villageId": self.village.id,
                "definitionVersionId": version.id,
                "censusDate": "2026-05-19",
                "formData": form_data,
            }
        )

        fields = result.data["submitVillageCensusSnapshotV2"]["result"]["fields"]
        self.assertEqual(fields[0]["name"], "form_data.rows")
        self.assertFalse(VillageCensusSnapshot.objects.exists())

    def test_submit_v2_rejects_unknown_animal_species(self):
        self.enable_census()
        cattle, buffalo = self.create_species()
        _definition, version = self.create_animal_definition()
        self.client.authenticate(self.reporter)
        form_data = self.animal_form_data(cattle, buffalo)
        form_data["rows"][1]["species_id"] = 999999

        result = self.execute_submit_v2(
            {
                "villageId": self.village.id,
                "definitionVersionId": version.id,
                "censusDate": "2026-05-19",
                "formData": form_data,
            }
        )

        fields = result.data["submitVillageCensusSnapshotV2"]["result"]["fields"]
        self.assertEqual(fields[0]["name"], "form_data.rows")
        self.assertFalse(VillageCensusSnapshot.objects.exists())

    def test_submit_v2_rejects_negative_integer_measure(self):
        self.enable_census()
        cattle, buffalo = self.create_species()
        _definition, version = self.create_animal_definition()
        self.client.authenticate(self.reporter)
        form_data = self.animal_form_data(cattle, buffalo)
        form_data["rows"][0]["measures"]["animal_quantity"] = -1

        result = self.execute_submit_v2(
            {
                "villageId": self.village.id,
                "definitionVersionId": version.id,
                "censusDate": "2026-05-19",
                "formData": form_data,
            }
        )

        fields = result.data["submitVillageCensusSnapshotV2"]["result"]["fields"]
        self.assertEqual(fields[0]["name"], "form_data.rows")
        self.assertFalse(VillageCensusSnapshot.objects.exists())

    def test_current_animal_fact_pointers_are_replaced_by_newer_submit(self):
        self.enable_census()
        cattle, buffalo = self.create_species()
        _definition, version = self.create_animal_definition()
        self.client.authenticate(self.reporter)
        self.execute_submit_v2(
            {
                "villageId": self.village.id,
                "definitionVersionId": version.id,
                "censusDate": "2026-05-18",
                "formData": self.animal_form_data(cattle, buffalo),
            }
        )
        second_form_data = self.animal_form_data(cattle, buffalo)
        second_form_data["rows"][0]["measures"]["animal_quantity"] = 99
        self.execute_submit_v2(
            {
                "villageId": self.village.id,
                "definitionVersionId": version.id,
                "censusDate": "2026-05-19",
                "formData": second_form_data,
            }
        )
        query = """
        query currentAnimalCensusFacts($villageId: Int!) {
            currentAnimalCensusFacts(villageId: $villageId) {
                fact {
                    rowKey
                    measures
                }
            }
        }
        """

        result = self.client.execute(query, {"villageId": self.village.id})

        self.assertIsNone(result.errors, result.errors)
        current_facts = result.data["currentAnimalCensusFacts"]
        self.assertEqual(len(current_facts), 2)
        cattle_fact = next(
            fact for fact in current_facts if fact["fact"]["rowKey"] == "species:CATTLE"
        )
        self.assertEqual(cattle_fact["fact"]["measures"]["animal_quantity"], 99)
