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
            },
            published_at=timezone.now(),
        )
        return definition, version

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

    def test_latest_village_census_v2_returns_row_backed_animal_snapshot(self):
        self.enable_census()
        _definition, version = self.create_animal_definition()
        old_snapshot = VillageCensusSnapshot.objects.create(
            village=self.village,
            reporter=self.reporter,
            definition_version=version,
            census_date="2026-05-01",
        )
        AnimalCensusFact.objects.create(
            snapshot=old_snapshot,
            row_key="species:CATTLE",
            row_label="Cattle",
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
            row_key="species:CATTLE",
            row_label="Cattle",
            measures={"animal_quantity": 0, "household_quantity": 0},
        )
        AnimalCensusFact.objects.create(
            snapshot=latest_snapshot,
            row_key="species:BUFFALO",
            row_label="Buffalo",
            measures={"animal_quantity": 7, "household_quantity": 3},
        )
        self.client.authenticate(self.reporter)
        query = """
        query latestVillageCensusV2($villageId: Int!) {
            latestVillageCensusV2(villageId: $villageId, kind: "ANIMAL") {
                censusDate
                facts {
                    rowKey
                    rowLabel
                    animalQuantity
                    householdQuantity
                }
            }
        }
        """

        result = self.client.execute(query, {"villageId": self.village.id})

        self.assertIsNone(result.errors, result.errors)
        latest = result.data["latestVillageCensusV2"]
        self.assertEqual(latest["censusDate"], "2026-05-05")
        facts = sorted(latest["facts"], key=lambda fact: fact["rowKey"])
        self.assertEqual(
            facts,
            [
                {
                    "rowKey": "species:BUFFALO",
                    "rowLabel": "Buffalo",
                    "animalQuantity": 7,
                    "householdQuantity": 3,
                },
                {
                    "rowKey": "species:CATTLE",
                    "rowLabel": "Cattle",
                    "animalQuantity": 0,
                    "householdQuantity": 0,
                },
            ],
        )

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
