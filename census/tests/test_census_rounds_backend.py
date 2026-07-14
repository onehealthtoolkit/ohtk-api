from graphql_jwt.testcases import JSONWebTokenTestCase

from accounts.models import Authority, AuthorityUser, Village, VillageReporterAssignment
from accounts.village_capability import set_village_capability_enabled
from census.animal_census_capability import set_animal_census_capability_enabled
from census.models import (
    CensusDefinition,
    CensusDefinitionVersion,
    CensusRoundDefinition,
    CurrentAnimalCensusFact,
    VillageCensusSnapshot,
)
from census.rounds import (
    materialize_occurrence,
    parse_month_day,
    validate_round_definition,
)


class CensusRoundsBackendTests(JSONWebTokenTestCase):
    def setUp(self):
        self.authority = Authority.objects.create(name="test authority", code="TA")
        self.other_authority = Authority.objects.create(name="other", code="OA")
        self.village = Village.objects.create(
            code="V001", name="Village One", authority=self.authority
        )
        self.missing_village = Village.objects.create(
            code="V002", name="Village Two", authority=self.authority
        )
        self.outside_village = Village.objects.create(
            code="V999", name="Outside", authority=self.other_authority
        )
        self.reporter = AuthorityUser.objects.create(
            username="official-reporter",
            authority=self.authority,
            role=AuthorityUser.Role.REPORTER,
        )
        self.officer = AuthorityUser.objects.create(
            username="officer",
            authority=self.authority,
            role=AuthorityUser.Role.OFFICER,
        )
        self.admin = AuthorityUser.objects.create(
            username="admin",
            authority=self.authority,
            role=AuthorityUser.Role.ADMIN,
        )
        self.super_user = AuthorityUser.objects.create(
            username="platform",
            authority=self.authority,
            role=AuthorityUser.Role.ADMIN,
            is_superuser=True,
        )
        VillageReporterAssignment.objects.create(
            reporter=self.reporter,
            village=self.village,
            census_role=VillageReporterAssignment.CensusRole.OFFICIAL,
        )
        set_village_capability_enabled(True)
        set_animal_census_capability_enabled(True)
        self.definition, self.version = self.create_animal_definition()

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
                    }
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
        )
        return definition, version

    def create_round(self, mode=CensusRoundDefinition.Mode.PRODUCTION):
        round_definition = CensusRoundDefinition.objects.create(
            code=f"ANIMAL_{mode}",
            name=f"Animal {mode}",
            kind=CensusDefinition.Kind.ANIMAL,
            mode=mode,
            census_period_start="01-01",
            census_period_end="06-30",
            start_date="05-01",
            soft_finish_date="05-20",
            hard_finish_date="05-31",
            enabled=True,
        )
        return materialize_occurrence(round_definition, 2026)

    def animal_form_data(self, animal_quantity=10):
        return {
            "summary": {
                "village_household_quantity": 120,
                "animal_household_quantity": 72,
            },
            "rows": [
                {
                    "row_key": "species:CATTLE",
                    "measures": {
                        "animal_quantity": animal_quantity,
                        "household_quantity": 4,
                    },
                }
            ],
        }

    def submit_snapshot(self, census_date, occurrence_id=None, animal_quantity=10):
        mutation = """
        mutation submitVillageCensusSnapshotV2(
            $villageId: Int!,
            $definitionVersionId: Int!,
            $occurrenceId: Int,
            $censusDate: Date!,
            $formData: GenericScalar!
        ) {
            submitVillageCensusSnapshotV2(
                villageId: $villageId,
                definitionVersionId: $definitionVersionId,
                occurrenceId: $occurrenceId,
                censusDate: $censusDate,
                formData: $formData
            ) {
                result {
                    __typename
                    ... on VillageCensusSnapshotType {
                        id
                        roundResolution
                        roundOccurrence {
                            id
                            occurrenceKey
                            mode
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
        variables = {
            "villageId": self.village.id,
            "definitionVersionId": self.version.id,
            "occurrenceId": occurrence_id,
            "censusDate": census_date,
            "formData": self.animal_form_data(animal_quantity),
        }
        return self.client.execute(mutation, variables)

    def test_admin_can_save_round_definition_and_materialize_years(self):
        self.client.authenticate(self.super_user)
        mutation = """
        mutation saveRound {
            adminCensusRoundDefinitionSave(
                code: "ANIMAL_H1",
                name: "H1 Animal Census",
                kind: "ANIMAL",
                mode: "PRODUCTION",
                censusPeriodStart: "01-01",
                censusPeriodEnd: "06-30",
                startDate: "05-01",
                softFinishDate: "05-20",
                hardFinishDate: "05-31",
                materializeFromYear: 2026,
                materializeYears: 2
            ) {
                definition {
                    code
                }
                occurrences {
                    occurrenceKey
                    startDate
                    hardFinishDate
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
        payload = result.data["adminCensusRoundDefinitionSave"]
        self.assertEqual(payload["fields"], [])
        self.assertEqual(payload["definition"]["code"], "ANIMAL_H1")
        self.assertEqual(
            [occurrence["occurrenceKey"] for occurrence in payload["occurrences"]],
            ["ANIMAL_H1_2026", "ANIMAL_H1_2027"],
        )

    def test_overlapping_production_round_definition_is_rejected(self):
        self.create_round()
        self.client.authenticate(self.super_user)
        mutation = """
        mutation saveRound {
            adminCensusRoundDefinitionSave(
                code: "ANIMAL_OVERLAP",
                name: "Overlap",
                kind: "ANIMAL",
                mode: "PRODUCTION",
                censusPeriodStart: "01-01",
                censusPeriodEnd: "06-30",
                startDate: "05-10",
                softFinishDate: "05-20",
                hardFinishDate: "06-01"
            ) {
                fields {
                    name
                    message
                }
            }
        }
        """

        result = self.client.execute(mutation)

        self.assertIsNone(result.errors, result.errors)
        fields = result.data["adminCensusRoundDefinitionSave"]["fields"]
        self.assertEqual(fields[0]["name"], "start_date")

    def test_submission_with_explicit_occurrence_links_snapshot(self):
        occurrence = self.create_round()
        self.client.authenticate(self.reporter)

        result = self.submit_snapshot("2026-05-19", occurrence_id=occurrence.id)

        self.assertIsNone(result.errors, result.errors)
        snapshot = result.data["submitVillageCensusSnapshotV2"]["result"]
        self.assertEqual(snapshot["__typename"], "VillageCensusSnapshotType")
        self.assertEqual(snapshot["roundResolution"], "EXPLICIT")
        self.assertEqual(snapshot["roundOccurrence"]["occurrenceKey"], occurrence.occurrence_key)

    def test_submission_without_occurrence_infers_single_open_round(self):
        occurrence = self.create_round()
        self.client.authenticate(self.reporter)

        result = self.submit_snapshot("2026-05-19")

        self.assertIsNone(result.errors, result.errors)
        snapshot = result.data["submitVillageCensusSnapshotV2"]["result"]
        self.assertEqual(snapshot["__typename"], "VillageCensusSnapshotType")
        self.assertEqual(snapshot["roundResolution"], "INFERRED")
        self.assertEqual(snapshot["roundOccurrence"]["occurrenceKey"], occurrence.occurrence_key)

    def test_submission_after_hard_finish_is_rejected(self):
        occurrence = self.create_round()
        self.client.authenticate(self.reporter)

        result = self.submit_snapshot("2026-06-01", occurrence_id=occurrence.id)

        self.assertIsNone(result.errors, result.errors)
        fields = result.data["submitVillageCensusSnapshotV2"]["result"]["fields"]
        self.assertEqual(fields[0]["name"], "occurrence_id")
        self.assertEqual(
            fields[0]["message"], "census round is not open for submitted census date"
        )

    def test_training_submission_does_not_update_production_latest_or_current(self):
        production = self.create_round()
        training = self.create_round(mode=CensusRoundDefinition.Mode.TRAINING)
        self.client.authenticate(self.reporter)
        self.submit_snapshot("2026-05-19", occurrence_id=production.id, animal_quantity=5)
        self.submit_snapshot("2026-05-19", occurrence_id=training.id, animal_quantity=99)
        query = """
        query latest($villageId: Int!) {
            latestVillageCensusV2(villageId: $villageId, kind: "ANIMAL") {
                roundOccurrence {
                    mode
                }
            }
            currentAnimalCensusFacts(villageId: $villageId) {
                fact {
                    measures
                }
            }
        }
        """

        result = self.client.execute(query, {"villageId": self.village.id})

        self.assertIsNone(result.errors, result.errors)
        self.assertEqual(
            result.data["latestVillageCensusV2"]["roundOccurrence"]["mode"],
            "PRODUCTION",
        )
        self.assertEqual(CurrentAnimalCensusFact.objects.count(), 1)
        self.assertEqual(
            result.data["currentAnimalCensusFacts"][0]["fact"]["measures"][
                "animal_quantity"
            ],
            5,
        )

    def test_coverage_query_counts_missing_submitted_and_late_rows(self):
        occurrence = self.create_round()
        self.client.authenticate(self.reporter)
        self.submit_snapshot("2026-05-25", occurrence_id=occurrence.id)
        self.client.authenticate(self.officer)
        query = """
        query coverage($occurrenceId: Int!) {
            censusRoundCoverage(occurrenceId: $occurrenceId, limit: 20) {
                totalCount
                submittedCount
                missingCount
                lateCount
                rows {
                    status
                    village {
                        code
                    }
                    villageHouseholdQuantity
                    animalHouseholdQuantity
                    totalAnimalQuantity
                    speciesSummary
                }
            }
        }
        """

        result = self.client.execute(query, {"occurrenceId": occurrence.id})

        self.assertIsNone(result.errors, result.errors)
        coverage = result.data["censusRoundCoverage"]
        self.assertEqual(coverage["totalCount"], 2)
        self.assertEqual(coverage["submittedCount"], 1)
        self.assertEqual(coverage["missingCount"], 1)
        self.assertEqual(coverage["lateCount"], 1)
        rows_by_code = {row["village"]["code"]: row for row in coverage["rows"]}
        self.assertEqual(rows_by_code["V001"]["status"], "SUBMITTED_LATE")
        self.assertEqual(rows_by_code["V001"]["villageHouseholdQuantity"], 120)
        self.assertEqual(rows_by_code["V001"]["totalAnimalQuantity"], 10)
        self.assertEqual(rows_by_code["V002"]["status"], "MISSING")

    def test_parse_month_day_rejects_leap_day(self):
        with self.assertRaises(ValueError) as raised:
            parse_month_day("02-29")
        self.assertIn("leap day", str(raised.exception))

    def test_validate_round_definition_rejects_leap_day_without_crash(self):
        definition = CensusRoundDefinition(
            code="LEAP",
            name="Leap",
            kind=CensusDefinition.Kind.ANIMAL,
            mode=CensusRoundDefinition.Mode.PRODUCTION,
            census_period_start="02-29",
            census_period_end="03-01",
            start_date="02-29",
            soft_finish_date="03-01",
            hard_finish_date="03-15",
            enabled=True,
        )

        errors = validate_round_definition(definition)

        self.assertTrue(errors)
        self.assertEqual(errors[0][0], "census_period_start")
        self.assertIn("MM-DD", errors[0][1])
