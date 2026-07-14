from datetime import date
from types import SimpleNamespace

from django.utils import timezone
from django.db import IntegrityError, transaction
from graphql_jwt.testcases import JSONWebTokenTestCase

from census.animal_census_capability import set_animal_census_capability_enabled
from accounts.models import (
    Authority,
    AuthorityUser,
    Village,
    VillageReporterAssignment,
)
from accounts.village_capability import set_village_capability_enabled
from census.definition_schema import generate_runtime_schema
from census.models import (
    AnimalCensusFact,
    CensusDefinition,
    CensusDefinitionVersion,
    CensusRoundDefinition,
    CurrentAnimalCensusFact,
    CurrentHumanCensusFact,
    HumanCensusFact,
    VillageCensusSnapshot,
)
from census.rounds import materialize_occurrence


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
        cattle = SimpleNamespace(code="CATTLE", name="Cattle", row_key="species:CATTLE")
        buffalo = SimpleNamespace(
            code="BUFFALO", name="Buffalo", row_key="species:BUFFALO"
        )
        return cattle, buffalo

    def create_round_definition(self, kind, code):
        definition = CensusRoundDefinition.objects.create(
            code=code,
            name=f"{code} round",
            kind=kind,
            mode=CensusRoundDefinition.Mode.PRODUCTION,
            census_period_start="01-01",
            census_period_end="06-30",
            start_date="05-01",
            soft_finish_date="05-20",
            hard_finish_date="05-31",
            enabled=True,
        )
        return materialize_occurrence(definition, 2026)

    def create_animal_definition(self, with_round=True):
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
                "rows": [
                    {
                        "key": "species:CATTLE",
                        "row_key": "species:CATTLE",
                        "label": "Cattle",
                        "dimensions": {"species": "CATTLE"},
                    },
                    {
                        "key": "species:BUFFALO",
                        "row_key": "species:BUFFALO",
                        "label": "Buffalo",
                        "dimensions": {"species": "BUFFALO"},
                    },
                ],
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
        if with_round:
            self.create_round_definition(CensusDefinition.Kind.ANIMAL, "ANIMAL_H1")
        return definition, version

    def create_authored_animal_definition(self, with_round=True):
        definition = CensusDefinition.objects.create(
            kind=CensusDefinition.Kind.ANIMAL,
            enabled=True,
            sort_order=1,
        )
        definition_schema = {
            "schema_version": 1,
            "dimensions": [
                {
                    "key": "species",
                    "label": {"default": "Species"},
                    "values": [
                        {"key": "CATTLE", "label": {"default": "Cattle"}},
                        {"key": "BUFFALO", "label": {"default": "Buffalo"}},
                    ],
                }
            ],
            "measures": [
                {
                    "key": "animal_quantity",
                    "label": {"default": "Animal quantity"},
                    "type": "integer",
                    "required": True,
                },
                {
                    "key": "household_quantity",
                    "label": {"default": "Households"},
                    "type": "integer",
                    "required": True,
                },
            ],
        }
        version = CensusDefinitionVersion.objects.create(
            definition=definition,
            version=1,
            status=CensusDefinitionVersion.Status.PUBLISHED,
            schema=generate_runtime_schema(definition_schema),
            definition_schema=definition_schema,
            published_at=timezone.now(),
        )
        if with_round:
            self.create_round_definition(CensusDefinition.Kind.ANIMAL, "ANIMAL_H1")
        return definition, version

    def create_human_definition(self, with_round=True):
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
                        "key": "total",
                        "label": "Total",
                        "dimensions": {},
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
        if with_round:
            self.create_round_definition(CensusDefinition.Kind.HUMAN, "HUMAN_H1")
        return definition, version

    def animal_form_data(self, cattle, buffalo):
        return {
            "summary": {
                "village_household_quantity": 120,
                "animal_household_quantity": 72,
            },
            "rows": [
                {
                    "row_key": cattle.row_key,
                    "measures": {
                        "animal_quantity": 10,
                        "household_quantity": 4,
                    },
                },
                {
                    "row_key": buffalo.row_key,
                    "measures": {
                        "animal_quantity": 2,
                        "household_quantity": 1,
                    },
                },
            ],
        }

    def animal_row_key_form_data(self):
        return {
            "summary": {
                "village_household_quantity": 120,
                "animal_household_quantity": 72,
            },
            "rows": [
                {
                    "row_key": "species:CATTLE",
                    "measures": {
                        "animal_quantity": 10,
                        "household_quantity": 4,
                    },
                },
                {
                    "row_key": "species:BUFFALO",
                    "measures": {
                        "animal_quantity": 2,
                        "household_quantity": 1,
                    },
                },
            ],
        }

    def human_form_data(self):
        return {
            "rows": [
                {"row_key": "total", "measures": {"population": 45}},
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
                        villageHouseholdQuantity
                        animalHouseholdQuantity
                        definitionVersion {
                            version
                            definition {
                                kind
                            }
                        }
                        roundOccurrence {
                            occurrenceKey
                            mode
                        }
                        roundResolution
                        facts {
                            rowKey
                            rowLabel
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
        self.assertEqual(version["schema"]["rows"][0]["row_key"], "species:CATTLE")
        self.assertEqual(
            version["runtimeSchema"]["rows"][0]["row_key"], "species:CATTLE"
        )
        self.assertEqual(result.data["censusDefinitions"][0]["kind"], "ANIMAL")

    def test_reporter_submit_animal_census_requires_household_summary(self):
        self.enable_census()
        _definition, version = self.create_animal_definition()
        self.client.authenticate(self.reporter)
        form_data = self.animal_row_key_form_data()
        form_data.pop("summary")

        result = self.execute_submit_v2(
            {
                "villageId": self.village.id,
                "definitionVersionId": version.id,
                "censusDate": "2026-05-21",
                "formData": form_data,
            }
        )

        self.assertIsNone(result.errors, result.errors)
        payload = result.data["submitVillageCensusSnapshotV2"]["result"]
        self.assertEqual(payload["__typename"], "VillageCensusSnapshotProblem")
        self.assertEqual(
            payload["fields"][0]["message"],
            "animal census household summary is required",
        )

    def test_reporter_submit_animal_census_returns_household_summary(self):
        self.enable_census()
        _definition, version = self.create_animal_definition()
        self.client.authenticate(self.reporter)

        result = self.execute_submit_v2(
            {
                "villageId": self.village.id,
                "definitionVersionId": version.id,
                "censusDate": "2026-05-21",
                "formData": self.animal_row_key_form_data(),
            }
        )

        self.assertIsNone(result.errors, result.errors)
        payload = result.data["submitVillageCensusSnapshotV2"]["result"]
        self.assertEqual(payload["__typename"], "VillageCensusSnapshotType")
        self.assertEqual(payload["villageHouseholdQuantity"], 120)
        self.assertEqual(payload["animalHouseholdQuantity"], 72)
        snapshot = VillageCensusSnapshot.objects.get(pk=payload["id"])
        self.assertEqual(
            snapshot.form_data["summary"],
            {
                "village_household_quantity": 120,
                "animal_household_quantity": 72,
            },
        )

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
        self.assertEqual(
            [summary["kind"] for summary in summaries], ["ANIMAL", "HUMAN"]
        )
        human = summaries[1]
        self.assertEqual(human["latestSnapshot"]["censusDate"], "2026-05-19")
        self.assertEqual(
            human["latestSnapshot"]["definitionVersion"]["definition"]["kind"],
            "HUMAN",
        )

    def test_disabling_human_keeps_animal_active_for_mobile(self):
        self.enable_census()
        self.create_animal_definition()
        human_definition, human_version = self.create_human_definition()
        VillageCensusSnapshot.objects.create(
            village=self.village,
            reporter=self.reporter,
            definition_version=human_version,
            census_date=date(2026, 5, 19),
        )
        human_definition.enabled = False
        human_definition.save(update_fields=["enabled"])
        self.client.authenticate(self.reporter)

        summary_result = self.execute_active_kind_summary()
        version_result = self.client.execute(
            """
            query activeHumanDefinition($villageId: Int!, $kind: String!) {
                activeCensusDefinitionVersion(kind: $kind) {
                    id
                }
                latestVillageCensusV2(villageId: $villageId, kind: $kind) {
                    id
                    censusDate
                    definitionVersion {
                        definition {
                            kind
                        }
                    }
                }
                censusDefinitions {
                    kind
                    enabled
                }
            }
            """,
            {"villageId": self.village.id, "kind": "HUMAN"},
        )

        self.assertIsNone(summary_result.errors, summary_result.errors)
        self.assertEqual(
            [
                summary["kind"]
                for summary in summary_result.data["activeVillageCensusDefinitions"]
            ],
            ["ANIMAL"],
        )
        self.assertIsNone(version_result.errors, version_result.errors)
        self.assertIsNone(version_result.data["activeCensusDefinitionVersion"])
        self.assertEqual(
            version_result.data["latestVillageCensusV2"]["definitionVersion"][
                "definition"
            ]["kind"],
            "HUMAN",
        )
        self.assertEqual(
            [
                definition["kind"]
                for definition in version_result.data["censusDefinitions"]
            ],
            ["ANIMAL"],
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

    def test_admin_can_ensure_default_definitions(self):
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
                    definitionSchema
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
        # Default animal schema is Option A (group HH + species heads)
        authored = animal_version["definitionSchema"]
        self.assertEqual(authored.get("schema_version"), 2)
        self.assertEqual(authored["groups"][0]["key"], "LARGE_RUMINANT")
        runtime_rows = {
            row.get("row_key") or row.get("key"): row
            for row in animal_version["runtimeSchema"]["rows"]
        }
        self.assertIn("group:LARGE_RUMINANT", runtime_rows)
        self.assertIn("species:CATTLE", runtime_rows)
        self.assertEqual(
            runtime_rows["species:CATTLE"]["dimensions"]["species"], "CATTLE"
        )
        self.assertEqual(
            animal_version["schema"]["layout"], "grouped_species"
        )

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

    def test_admin_can_publish_authored_human_schema_version(self):
        super_user = AuthorityUser.objects.create(
            username="authored-schema-admin",
            authority=self.authority,
            role=AuthorityUser.Role.ADMIN,
            is_superuser=True,
        )
        self.client.authenticate(super_user)
        mutation = """
        mutation publishHumanSchema($definitionSchema: GenericScalar!) {
            adminCensusDefinitionVersionPublish(
                kind: "HUMAN",
                definitionSchema: $definitionSchema
            ) {
                version {
                    version
                    definitionSchema
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
        definition_schema = {
            "schema_version": 1,
            "dimensions": [
                {
                    "key": "gender",
                    "label": {"default": "Gender", "la": "ເພດ"},
                    "values": [
                        {"key": "male", "label": {"default": "Male", "la": "ຊາຍ"}},
                        {"key": "female", "label": {"default": "Female", "la": "ຍິງ"}},
                    ],
                }
            ],
            "measures": [
                {
                    "key": "population",
                    "label": {"default": "Population", "la": "ປະຊາກອນ"},
                    "type": "integer",
                    "required": True,
                }
            ],
        }

        result = self.client.execute(mutation, {"definitionSchema": definition_schema})

        self.assertIsNone(result.errors, result.errors)
        payload = result.data["adminCensusDefinitionVersionPublish"]
        self.assertEqual(payload["fields"], [])
        version = payload["version"]
        self.assertEqual(version["definitionSchema"]["dimensions"][0]["key"], "gender")
        self.assertEqual(version["schema"]["rows"][0]["key"], "gender:male")
        self.assertEqual(version["schema"]["rows"][0]["dimensions"], {"gender": "male"})
        self.assertEqual(version["runtimeSchema"]["rows"][1]["label"], "Female")

    def test_admin_can_disable_human_definition_without_publishing_new_version(self):
        self.enable_census()
        _animal_definition, _animal_version = self.create_animal_definition()
        human_definition, human_version = self.create_human_definition()
        super_user = AuthorityUser.objects.create(
            username="schema-admin-disable",
            authority=self.authority,
            role=AuthorityUser.Role.ADMIN,
            is_superuser=True,
        )
        self.client.authenticate(super_user)
        mutation = """
        mutation setHumanEnabled($enabled: Boolean!) {
            adminCensusDefinitionSetEnabled(kind: "HUMAN", enabled: $enabled) {
                definition {
                    id
                    kind
                    enabled
                }
                version {
                    id
                    version
                    status
                    definition {
                        kind
                    }
                }
                fields {
                    name
                    message
                }
            }
        }
        """

        result = self.client.execute(mutation, {"enabled": False})

        self.assertIsNone(result.errors, result.errors)
        payload = result.data["adminCensusDefinitionSetEnabled"]
        self.assertEqual(payload["fields"], [])
        self.assertEqual(payload["definition"]["kind"], "HUMAN")
        self.assertFalse(payload["definition"]["enabled"])
        self.assertEqual(payload["version"]["id"], str(human_version.id))
        self.assertEqual(payload["version"]["version"], 1)
        self.assertEqual(
            CensusDefinitionVersion.objects.filter(definition=human_definition).count(),
            1,
        )
        human_definition.refresh_from_db()
        human_version.refresh_from_db()
        self.assertFalse(human_definition.enabled)
        self.assertEqual(human_version.status, CensusDefinitionVersion.Status.PUBLISHED)

        query = """
        query humanDefinitionDisabled {
            censusDefinitions {
                kind
                enabled
            }
            activeCensusDefinitionVersion(kind: "HUMAN") {
                id
            }
        }
        """
        query_result = self.client.execute(query)

        self.assertIsNone(query_result.errors, query_result.errors)
        self.assertIsNone(query_result.data["activeCensusDefinitionVersion"])
        self.assertEqual(
            {
                definition["kind"]: definition["enabled"]
                for definition in query_result.data["censusDefinitions"]
            },
            {"ANIMAL": True, "HUMAN": False},
        )

    def test_census_definition_kind_is_unique(self):
        CensusDefinition.objects.create(kind=CensusDefinition.Kind.ANIMAL)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CensusDefinition.objects.create(kind=CensusDefinition.Kind.ANIMAL)

    def test_official_reporter_can_submit_animal_snapshot_and_current_fact_pointers(
        self,
    ):
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
        self.assertEqual(snapshot["formData"]["rows"][0]["row_key"], cattle.row_key)
        self.assertEqual(len(snapshot["facts"]), 2)
        cattle_fact = next(
            fact for fact in snapshot["facts"] if fact["rowKey"] == "species:CATTLE"
        )
        self.assertEqual(cattle_fact["rowLabel"], "Cattle")
        self.assertEqual(cattle_fact["animalQuantity"], 10)
        self.assertTrue(
            AnimalCensusFact.objects.filter(
                row_key="species:CATTLE",
                row_label="Cattle",
                extra_dimensions={"species": "CATTLE"},
                measures={"animal_quantity": 10, "household_quantity": 4},
            ).exists()
        )
        self.assertEqual(CurrentAnimalCensusFact.objects.count(), 2)

    def test_official_reporter_can_submit_authored_animal_snapshot_by_row_key(
        self,
    ):
        self.enable_census()
        cattle, _buffalo = self.create_species()
        _definition, version = self.create_authored_animal_definition()
        self.client.authenticate(self.reporter)

        result = self.execute_submit_v2(
            {
                "villageId": self.village.id,
                "definitionVersionId": version.id,
                "censusDate": "2026-05-19",
                "formData": self.animal_row_key_form_data(),
            }
        )

        self.assertIsNone(result.errors, result.errors)
        snapshot = result.data["submitVillageCensusSnapshotV2"]["result"]
        self.assertEqual(snapshot["__typename"], "VillageCensusSnapshotType")
        self.assertEqual(snapshot["definitionVersion"]["definition"]["kind"], "ANIMAL")
        cattle_fact = next(
            fact for fact in snapshot["facts"] if fact["rowKey"] == "species:CATTLE"
        )
        self.assertEqual(cattle_fact["rowLabel"], "Cattle")
        self.assertEqual(cattle_fact["extraDimensions"], {"species": "CATTLE"})
        self.assertTrue(
            AnimalCensusFact.objects.filter(
                row_key="species:CATTLE",
                row_label="Cattle",
                extra_dimensions={"species": "CATTLE"},
                measures={"animal_quantity": 10, "household_quantity": 4},
            ).exists()
        )
        self.assertEqual(CurrentAnimalCensusFact.objects.count(), 2)

    def test_authored_animal_definition_is_stable_without_species_catalog(self):
        self.enable_census()
        cattle, buffalo = self.create_species()
        _definition, version = self.create_authored_animal_definition()
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
        self.assertEqual(len(snapshot["facts"]), 2)
        self.assertEqual(
            {fact["rowKey"] for fact in snapshot["facts"]},
            {"species:CATTLE", "species:BUFFALO"},
        )
        self.assertTrue(
            AnimalCensusFact.objects.filter(
                row_key="species:CATTLE",
                row_label="Cattle",
                extra_dimensions={"species": "CATTLE"},
            ).exists()
        )
        self.assertTrue(
            AnimalCensusFact.objects.filter(
                row_key="species:BUFFALO",
                row_label="Buffalo",
                extra_dimensions={"species": "BUFFALO"},
            ).exists()
        )
        self.assertEqual(CurrentAnimalCensusFact.objects.count(), 2)

    def test_official_reporter_can_submit_human_snapshot_and_current_fact_pointers(
        self,
    ):
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
        self.assertEqual(len(snapshot["humanFacts"]), 1)
        total_fact = next(
            fact for fact in snapshot["humanFacts"] if fact["rowKey"] == "total"
        )
        self.assertEqual(total_fact["dimensions"], {})
        self.assertTrue(
            HumanCensusFact.objects.filter(
                row_key="total",
                dimensions={},
                measures={"population": 45},
            ).exists()
        )
        self.assertEqual(CurrentHumanCensusFact.objects.count(), 1)

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

    def test_submit_v2_rejects_unknown_animal_row_key(self):
        self.enable_census()
        cattle, buffalo = self.create_species()
        _definition, version = self.create_animal_definition()
        self.client.authenticate(self.reporter)
        form_data = self.animal_form_data(cattle, buffalo)
        form_data["rows"][1]["row_key"] = "species:FISH"

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

    def test_submit_v2_reports_stale_animal_form_when_row_missing(self):
        self.enable_census()
        cattle, buffalo = self.create_species()
        _definition, version = self.create_animal_definition()
        self.client.authenticate(self.reporter)
        form_data = self.animal_form_data(cattle, buffalo)
        form_data["rows"] = form_data["rows"][:1]

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
        self.assertEqual(fields[0]["message"], "ACTIVE_ANIMAL_SPECIES_CHANGED")
        self.assertFalse(VillageCensusSnapshot.objects.exists())

    def test_submit_v2_rejects_disabled_definition_with_stable_code(self):
        self.enable_census()
        human_definition, version = self.create_human_definition()
        human_definition.enabled = False
        human_definition.save(update_fields=["enabled"])
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
        fields = result.data["submitVillageCensusSnapshotV2"]["result"]["fields"]
        self.assertEqual(fields[0]["name"], "definition_version_id")
        self.assertEqual(fields[0]["message"], "DEFINITION_DISABLED")
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

    def test_current_animal_census_facts_require_village_permission(self):
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
        other_authority = Authority.objects.create(
            name="other authority", code="OA"
        )
        other_village = Village.objects.create(
            code="V999", name="Other Village", authority=other_authority
        )
        query = """
        query currentAnimalCensusFacts($villageId: Int!) {
            currentAnimalCensusFacts(villageId: $villageId) {
                fact {
                    rowKey
                }
            }
        }
        """

        denied = self.client.execute(query, {"villageId": other_village.id})

        self.assertIsNotNone(denied.errors)
        self.assertIn("Permission denied", str(denied.errors[0]))
