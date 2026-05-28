from graphql_jwt.testcases import JSONWebTokenTestCase
from django.utils import timezone

from census.animal_census_capability import (
    ANIMAL_CENSUS_CAPABILITY_KEY,
    is_animal_census_capability_enabled,
    set_animal_census_capability_enabled,
)
from accounts.models import (
    Authority,
    AuthorityUser,
    Configuration,
    User,
    Village,
    VillageReporterAssignment,
)
from accounts.village_capability import set_village_capability_enabled
from census.models import (
    AnimalCensusFact,
    AnimalSpecies,
    CensusDefinition,
    CensusDefinitionVersion,
    VillageCensusSnapshot,
)


class AnimalCensusBackendTests(JSONWebTokenTestCase):
    def setUp(self):
        self.super_user = User.objects.create(username="platform", is_superuser=True)
        self.authority = Authority.objects.create(name="test authority", code="TA")
        self.other_authority = Authority.objects.create(
            name="other authority", code="OA"
        )
        self.village = Village.objects.create(
            code="V001", name="Village One", authority=self.authority
        )
        self.other_village = Village.objects.create(
            code="V999", name="Other Village", authority=self.other_authority
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

    def execute_species_create(self, variables):
        mutation = """
        mutation adminAnimalSpeciesCreate(
            $code: String!,
            $name: String!,
            $active: Boolean,
            $sortOrder: Int
        ) {
            adminAnimalSpeciesCreate(
                code: $code,
                name: $name,
                active: $active,
                sortOrder: $sortOrder
            ) {
                result {
                    __typename
                    ... on AdminAnimalSpeciesCreateSuccess {
                        id
                        code
                        name
                        active
                        sortOrder
                    }
                    ... on AdminAnimalSpeciesCreateProblem {
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

    def execute_species_update(self, variables):
        mutation = """
        mutation adminAnimalSpeciesUpdate(
            $id: Int!,
            $code: String!,
            $name: String!,
            $active: Boolean!,
            $sortOrder: Int
        ) {
            adminAnimalSpeciesUpdate(
                id: $id,
                code: $code,
                name: $name,
                active: $active,
                sortOrder: $sortOrder
            ) {
                result {
                    __typename
                    ... on AdminAnimalSpeciesUpdateSuccess {
                        id
                        code
                        name
                        active
                        sortOrder
                    }
                    ... on AdminAnimalSpeciesUpdateProblem {
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

    def execute_submit(self, variables):
        mutation = """
        mutation submitVillageCensusSnapshot(
            $villageId: Int!,
            $censusDate: Date!,
            $facts: [AnimalCensusFactInput!]!
        ) {
            submitVillageCensusSnapshot(
                villageId: $villageId,
                censusDate: $censusDate,
                facts: $facts
            ) {
                result {
                    __typename
                    ... on VillageCensusSnapshotType {
                        id
                        censusDate
                        facts {
                            species {
                                code
                            }
                            animalQuantity
                            householdQuantity
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

    def fact_variables(self, cattle, buffalo):
        return [
            {
                "speciesId": cattle.id,
                "animalQuantity": 0,
                "householdQuantity": 0,
            },
            {
                "speciesId": buffalo.id,
                "animalQuantity": 7,
                "householdQuantity": 3,
            },
        ]

    def test_animal_census_capability_requires_village_capability(self):
        self.client.authenticate(self.super_user)
        mutation = """
        mutation adminAnimalCensusCapabilityUpdate($enabled: Boolean!) {
            adminAnimalCensusCapabilityUpdate(enabled: $enabled) {
                enabled
                fields {
                    name
                    message
                }
            }
        }
        """

        result = self.client.execute(mutation, {"enabled": True})

        self.assertIsNone(result.errors, result.errors)
        payload = result.data["adminAnimalCensusCapabilityUpdate"]
        self.assertFalse(payload["enabled"])
        self.assertEqual(payload["fields"][0]["name"], "animal_census_enabled")
        self.assertFalse(is_animal_census_capability_enabled())

    def test_animal_census_capability_can_be_enabled_when_village_enabled(self):
        set_village_capability_enabled(True)
        self.client.authenticate(self.super_user)
        mutation = """
        mutation adminAnimalCensusCapabilityUpdate($enabled: Boolean!) {
            adminAnimalCensusCapabilityUpdate(enabled: $enabled) {
                enabled
                fields {
                    name
                }
            }
        }
        """

        result = self.client.execute(mutation, {"enabled": True})

        self.assertIsNone(result.errors, result.errors)
        self.assertTrue(result.data["adminAnimalCensusCapabilityUpdate"]["enabled"])
        self.assertEqual(
            Configuration.objects.get(key=ANIMAL_CENSUS_CAPABILITY_KEY).value,
            "enable",
        )

    def test_admin_can_create_and_update_animal_species(self):
        self.client.authenticate(self.super_user)
        result = self.execute_species_create(
            {
                "code": "CATTLE",
                "name": "Cattle",
                "active": True,
                "sortOrder": 1,
            }
        )
        self.assertIsNone(result.errors, result.errors)
        species = result.data["adminAnimalSpeciesCreate"]["result"]
        self.assertEqual(species["__typename"], "AdminAnimalSpeciesCreateSuccess")

        result = self.execute_species_update(
            {
                "id": int(species["id"]),
                "code": "CATTLE",
                "name": "Cattle Updated",
                "active": False,
                "sortOrder": 2,
            }
        )

        self.assertIsNone(result.errors, result.errors)
        updated = result.data["adminAnimalSpeciesUpdate"]["result"]
        self.assertEqual(updated["name"], "Cattle Updated")
        self.assertFalse(updated["active"])

    def test_reporter_can_query_active_animal_species_when_census_enabled(self):
        self.enable_census()
        cattle, buffalo = self.create_species()
        buffalo.active = False
        buffalo.save()
        self.client.authenticate(self.reporter)
        query = """
        query animalSpecies {
            animalSpecies {
                id
                code
                name
                active
                sortOrder
            }
        }
        """

        result = self.client.execute(query)

        self.assertIsNone(result.errors, result.errors)
        self.assertEqual(len(result.data["animalSpecies"]), 1)
        self.assertEqual(result.data["animalSpecies"][0]["code"], cattle.code)

    def test_official_assigned_reporter_can_submit_complete_snapshot_with_zeros(self):
        self.enable_census()
        cattle, buffalo = self.create_species()
        self.client.authenticate(self.reporter)

        result = self.execute_submit(
            {
                "villageId": self.village.id,
                "censusDate": "2026-05-05",
                "facts": self.fact_variables(cattle, buffalo),
            }
        )

        self.assertIsNone(result.errors, result.errors)
        snapshot = result.data["submitVillageCensusSnapshot"]["result"]
        self.assertEqual(snapshot["__typename"], "VillageCensusSnapshotType")
        self.assertEqual(len(snapshot["facts"]), 2)
        self.assertTrue(
            AnimalCensusFact.objects.filter(
                animal_species=cattle,
                measures={"animal_quantity": 0, "household_quantity": 0},
            ).exists()
        )

    def test_submit_rejects_when_animal_census_disabled(self):
        set_village_capability_enabled(True)
        cattle, buffalo = self.create_species()
        self.client.authenticate(self.reporter)

        result = self.execute_submit(
            {
                "villageId": self.village.id,
                "censusDate": "2026-05-05",
                "facts": self.fact_variables(cattle, buffalo),
            }
        )

        self.assertIsNone(result.errors, result.errors)
        fields = result.data["submitVillageCensusSnapshot"]["result"]["fields"]
        self.assertEqual(fields[0]["name"], "animal_census_enabled")
        self.assertFalse(VillageCensusSnapshot.objects.exists())

    def test_submit_rejects_missing_active_species(self):
        self.enable_census()
        cattle, _buffalo = self.create_species()
        self.client.authenticate(self.reporter)

        result = self.execute_submit(
            {
                "villageId": self.village.id,
                "censusDate": "2026-05-05",
                "facts": [
                    {
                        "speciesId": cattle.id,
                        "animalQuantity": 1,
                        "householdQuantity": 1,
                    }
                ],
            }
        )

        fields = result.data["submitVillageCensusSnapshot"]["result"]["fields"]
        self.assertEqual(fields[0]["name"], "facts")
        self.assertFalse(VillageCensusSnapshot.objects.exists())

    def test_submit_rejects_when_no_active_species_configured(self):
        self.enable_census()
        self.client.authenticate(self.reporter)

        result = self.execute_submit(
            {
                "villageId": self.village.id,
                "censusDate": "2026-05-05",
                "facts": [],
            }
        )

        fields = result.data["submitVillageCensusSnapshot"]["result"]["fields"]
        self.assertEqual(fields[0]["name"], "facts")
        self.assertFalse(VillageCensusSnapshot.objects.exists())

    def test_submit_rejects_inactive_species(self):
        self.enable_census()
        cattle, buffalo = self.create_species()
        buffalo.active = False
        buffalo.save()
        self.client.authenticate(self.reporter)

        result = self.execute_submit(
            {
                "villageId": self.village.id,
                "censusDate": "2026-05-05",
                "facts": self.fact_variables(cattle, buffalo),
            }
        )

        fields = result.data["submitVillageCensusSnapshot"]["result"]["fields"]
        self.assertEqual(fields[0]["name"], "facts")
        self.assertFalse(VillageCensusSnapshot.objects.exists())

    def test_submit_rejects_volunteer_reporter(self):
        self.enable_census()
        cattle, buffalo = self.create_species()
        volunteer = AuthorityUser.objects.create(
            username="volunteer",
            authority=self.authority,
            role=AuthorityUser.Role.REPORTER,
        )
        VillageReporterAssignment.objects.create(
            reporter=volunteer,
            village=self.village,
            census_role=VillageReporterAssignment.CensusRole.VOLUNTEER,
        )
        self.client.authenticate(volunteer)

        result = self.execute_submit(
            {
                "villageId": self.village.id,
                "censusDate": "2026-05-05",
                "facts": self.fact_variables(cattle, buffalo),
            }
        )

        fields = result.data["submitVillageCensusSnapshot"]["result"]["fields"]
        self.assertEqual(fields[0]["name"], "village_id")
        self.assertFalse(VillageCensusSnapshot.objects.exists())

    def test_submit_rejects_unassigned_reporter(self):
        self.enable_census()
        cattle, buffalo = self.create_species()
        unassigned = AuthorityUser.objects.create(
            username="unassigned",
            authority=self.authority,
            role=AuthorityUser.Role.REPORTER,
        )
        self.client.authenticate(unassigned)

        result = self.execute_submit(
            {
                "villageId": self.village.id,
                "censusDate": "2026-05-05",
                "facts": self.fact_variables(cattle, buffalo),
            }
        )

        fields = result.data["submitVillageCensusSnapshot"]["result"]["fields"]
        self.assertEqual(fields[0]["name"], "village_id")
        self.assertFalse(VillageCensusSnapshot.objects.exists())

    def test_latest_village_census_v2_returns_newest_animal_snapshot(self):
        self.enable_census()
        cattle, buffalo = self.create_species()
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
                "measures": [],
                "extra_dimensions": [],
            },
            published_at=timezone.now(),
        )
        old_snapshot = VillageCensusSnapshot.objects.create(
            village=self.village,
            reporter=self.reporter,
            definition_version=version,
            census_date="2026-05-01",
        )
        AnimalCensusFact.objects.create(
            snapshot=old_snapshot,
            animal_species=cattle,
            row_key="species:CATTLE",
            measures={"animal_quantity": 1, "household_quantity": 1},
        )
        AnimalCensusFact.objects.create(
            snapshot=old_snapshot,
            animal_species=buffalo,
            row_key="species:BUFFALO",
            measures={"animal_quantity": 1, "household_quantity": 1},
        )
        latest_snapshot = VillageCensusSnapshot.objects.create(
            village=self.village,
            reporter=self.reporter,
            definition_version=version,
            census_date="2026-05-05",
        )
        AnimalCensusFact.objects.create(
            snapshot=latest_snapshot,
            animal_species=cattle,
            row_key="species:CATTLE",
            measures={"animal_quantity": 0, "household_quantity": 0},
        )
        AnimalCensusFact.objects.create(
            snapshot=latest_snapshot,
            animal_species=buffalo,
            row_key="species:BUFFALO",
            measures={"animal_quantity": 7, "household_quantity": 3},
        )
        self.client.authenticate(self.reporter)
        query = """
        query latestVillageCensusV2($villageId: Int!) {
            latestVillageCensusV2(villageId: $villageId, kind: "ANIMAL") {
                censusDate
                facts {
                    species {
                        code
                    }
                    animalQuantity
                }
            }
        }
        """

        result = self.client.execute(query, {"villageId": self.village.id})

        self.assertIsNone(result.errors, result.errors)
        latest = result.data["latestVillageCensusV2"]
        self.assertEqual(latest["censusDate"], "2026-05-05")
        self.assertEqual(len(latest["facts"]), 2)

    def test_latest_village_census_v2_returns_null_for_unknown_village(self):
        self.enable_census()
        self.client.authenticate(self.reporter)
        query = """
        query latestVillageCensusV2($villageId: Int!) {
            latestVillageCensusV2(villageId: $villageId, kind: "ANIMAL") {
                id
            }
        }
        """

        result = self.client.execute(query, {"villageId": 999999})

        self.assertIsNone(result.errors, result.errors)
        self.assertIsNone(result.data["latestVillageCensusV2"])
