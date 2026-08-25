from datetime import date, datetime, timezone
from types import SimpleNamespace

from django.test import SimpleTestCase

from accounts.models import Village
from census.models import (
    AnimalCensusFact,
    CensusDefinition,
    CensusDefinitionVersion,
    CensusRoundDefinition,
    VillageCensusSnapshot,
)
from census.rounds import materialize_occurrence
from cases.models import Case
from reports.models import IncidentReport
from reports.tests.base_testcase import BaseTestCase
from summaries.lahis_summarized_table import (
    COL_AFFECTED_HOUSEHOLDS,
    COL_CLOSE_SOURCE,
    COL_DEAD_START,
    COL_POP_START,
    COL_RECOVER_START,
    COL_SICK_START,
    COL_STAMP_START,
    COL_VILLAGE_HOUSEHOLDS,
    COL_VILLAGE_POP_START,
    SPECIES_HEADERS,
    build_row_values,
    build_workbook,
    census_values_for_snapshot,
    collect_export_rows,
    format_close_source,
    normalize_species,
    parse_gps,
    resolve_report_census_snapshot,
    resolve_report_village_name,
    species_column_offset,
)


class LahisSummarizedTableUnitTests(SimpleTestCase):
    def test_normalize_species(self):
        self.assertEqual("Cattle", normalize_species("Cattle"))
        self.assertEqual("pig", normalize_species("Pig"))
        self.assertEqual("Goat-Sheep", normalize_species("Goat"))
        self.assertEqual("Goat-Sheep", normalize_species("Sheep"))
        self.assertIsNone(normalize_species("Dog"))
        self.assertIsNone(normalize_species(""))

    def test_parse_gps_lng_lat_order(self):
        lat, lng = parse_gps("100.25000,13.30000")
        self.assertEqual("13.30000", lat)
        self.assertEqual("100.25000", lng)

    def test_selected_report_village_wins_over_reporter_assignment(self):
        report = SimpleNamespace(
            village=SimpleNamespace(name="Selected village"),
            reported_by_id=7,
        )

        self.assertEqual(
            "Selected village",
            resolve_report_village_name(report, {7: "Assigned village"}),
        )

    def test_reporter_assignment_is_legacy_village_fallback(self):
        report = SimpleNamespace(village=None, reported_by_id=7)

        self.assertEqual(
            "Assigned village",
            resolve_report_village_name(report, {7: "Assigned village"}),
        )

    def test_census_snapshot_is_latest_not_after_incident_date(self):
        newer = SimpleNamespace(census_date=date(2026, 6, 1))
        applicable = SimpleNamespace(census_date=date(2026, 1, 1))
        report = SimpleNamespace(
            village_id=3,
            incident_date=datetime(2026, 3, 1, tzinfo=timezone.utc),
        )

        self.assertIs(
            applicable,
            resolve_report_census_snapshot(report, {3: [newer, applicable]}),
        )

    def test_census_values_keep_village_population_separate(self):
        facts = [
            SimpleNamespace(
                row_key="species:GOAT",
                extra_dimensions={"species": "GOAT"},
                measures={"animal_quantity": 5},
            ),
            SimpleNamespace(
                row_key="species:SHEEP",
                extra_dimensions={"species": "SHEEP"},
                measures={"animal_quantity": 7},
            ),
            SimpleNamespace(
                row_key="species:OTHER_POULTRY",
                extra_dimensions={"species": "OTHER_POULTRY"},
                measures={"animal_quantity": 8},
            ),
        ]
        snapshot = SimpleNamespace(
            form_data={"summary": {"village_household_quantity": 90}},
            facts=SimpleNamespace(all=lambda: facts),
        )

        village_households, population = census_values_for_snapshot(snapshot)

        self.assertEqual(90, village_households)
        self.assertEqual(12, population["Goat-Sheep"])
        self.assertEqual(8, population["Duck / other poultry"])

    def test_close_source_labels_are_lifecycle_values(self):
        self.assertEqual("Officer", format_close_source("officer"))
        self.assertEqual("System", format_close_source("system"))
        self.assertEqual("", format_close_source(""))
        self.assertEqual("", format_close_source("legacy-unknown"))

    def test_build_row_places_metrics_only_on_report_species(self):
        row = build_row_values(
            report_id=42,
            data={
                "animal_species": "Cattle",
                "num_household": 3,
                "num_total_animal": 10,
                "num_sick": 3,
                "num_dead": 1,
                "num_recover": 2,
            },
            incident_date=datetime(2026, 1, 15, 8, 0, tzinfo=timezone.utc),
            stopped_at=datetime(2026, 2, 1, 9, 0, tzinfo=timezone.utc),
            ai_suspected="FMD",
            test_result="lab negative",
            stamp_out=4,
            gps_location_str="102.60000,17.97000",
            province="Vientiane Capital",
            district="Sangthong",
            village="Ban Sangthong",
            village_households=80,
            village_animal_population={"Cattle": 120},
            close_source="officer",
        )
        self.assertEqual(49, len(row))
        self.assertEqual("42", row[0])
        self.assertEqual("Vientiane Capital", row[1])
        self.assertEqual("Sangthong", row[2])
        self.assertEqual("Ban Sangthong", row[3])
        self.assertEqual("17.97000", row[4])  # latitude
        self.assertEqual("102.60000", row[5])  # longitude
        self.assertEqual("FMD", row[8])
        self.assertEqual("lab negative", row[9])
        self.assertEqual(3, row[COL_AFFECTED_HOUSEHOLDS - 1])
        self.assertEqual(80, row[COL_VILLAGE_HOUSEHOLDS - 1])

        cattle = SPECIES_HEADERS.index("Cattle")
        # Cattle filled
        self.assertEqual(10, row[COL_POP_START - 1 + cattle])
        self.assertEqual(3, row[COL_SICK_START - 1 + cattle])
        self.assertEqual(1, row[COL_DEAD_START - 1 + cattle])
        self.assertEqual(2, row[COL_RECOVER_START - 1 + cattle])
        self.assertEqual(4, row[COL_STAMP_START - 1 + cattle])
        self.assertEqual(120, row[COL_VILLAGE_POP_START - 1 + cattle])
        self.assertEqual("Officer", row[COL_CLOSE_SOURCE - 1])
        # Other species empty for stamp-out block
        for i, name in enumerate(SPECIES_HEADERS):
            if name == "Cattle":
                continue
            self.assertEqual("", row[COL_STAMP_START - 1 + i], name)
            self.assertEqual("", row[COL_POP_START - 1 + i], name)

    def test_unmapped_species_leaves_metric_blocks_empty(self):
        row = build_row_values(
            report_id=1,
            data={"animal_species": "Dog", "num_sick": 9, "num_total_animal": 9},
            incident_date=None,
            stopped_at=None,
            ai_suspected="",
            test_result="",
            stamp_out=2,
            gps_location_str="",
            province="",
            district="",
            village="",
        )
        for i in range(6):
            self.assertEqual("", row[COL_POP_START - 1 + i])
            self.assertEqual("", row[COL_STAMP_START - 1 + i])

    def test_workbook_headers(self):
        wb = build_workbook([])
        ws = wb.active
        self.assertEqual("Animal sick", ws.cell(2, COL_SICK_START).value)
        self.assertEqual("Animal dead", ws.cell(2, COL_DEAD_START).value)
        self.assertEqual("Animal recoverd", ws.cell(2, COL_RECOVER_START).value)
        self.assertEqual(
            "Animals in affected households", ws.cell(2, COL_POP_START).value
        )
        self.assertEqual("Households", ws.cell(2, COL_AFFECTED_HOUSEHOLDS).value)
        self.assertEqual(
            "Village animal population", ws.cell(2, COL_VILLAGE_POP_START).value
        )
        self.assertEqual(
            "Duck / other poultry", ws.cell(3, COL_VILLAGE_POP_START + 5).value
        )
        self.assertEqual(
            "Affected households", ws.cell(3, COL_AFFECTED_HOUSEHOLDS).value
        )
        self.assertEqual(
            "Village households", ws.cell(3, COL_VILLAGE_HOUSEHOLDS).value
        )
        self.assertEqual("Case closure", ws.cell(2, COL_CLOSE_SOURCE).value)
        self.assertEqual("Close source", ws.cell(3, COL_CLOSE_SOURCE).value)
        self.assertEqual("Longitude", ws.cell(3, 6).value)
        self.assertEqual("suspected", ws.cell(3, 9).value)
        self.assertEqual(
            "Cattle",
            ws.cell(3, COL_POP_START + species_column_offset("Cattle")).value,
        )


class LahisSummarizedTableCensusIntegrationTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.village = Village.objects.create(
            code="V001", name="Selected village", authority=self.jatujak
        )
        definition = CensusDefinition.objects.create(
            kind=CensusDefinition.Kind.ANIMAL,
            enabled=True,
            sort_order=1,
        )
        version = CensusDefinitionVersion.objects.create(
            definition=definition,
            version=1,
            status=CensusDefinitionVersion.Status.PUBLISHED,
            schema={},
        )
        round_definition = CensusRoundDefinition.objects.create(
            code="ANIMAL_2026",
            name="Animal 2026",
            kind=CensusDefinition.Kind.ANIMAL,
            mode=CensusRoundDefinition.Mode.PRODUCTION,
            census_period_start="01-01",
            census_period_end="12-31",
            start_date="01-01",
            soft_finish_date="06-30",
            hard_finish_date="12-31",
            enabled=True,
        )
        occurrence = materialize_occurrence(round_definition, 2026)
        self._create_snapshot(
            version=version,
            occurrence=occurrence,
            census_date=date(2026, 1, 1),
            households=80,
            cattle=120,
        )
        self._create_snapshot(
            version=version,
            occurrence=occurrence,
            census_date=date(2026, 6, 1),
            households=90,
            cattle=140,
        )

    def _create_snapshot(
        self, *, version, occurrence, census_date, households, cattle
    ):
        snapshot = VillageCensusSnapshot.objects.create(
            village=self.village,
            reporter=self.jatujak_reporter,
            definition_version=version,
            round_occurrence=occurrence,
            census_date=census_date,
            form_data={
                "summary": {"village_household_quantity": households}
            },
        )
        AnimalCensusFact.objects.create(
            snapshot=snapshot,
            row_key="species:CATTLE",
            row_label="Cattle",
            extra_dimensions={"species": "CATTLE"},
            measures={"animal_quantity": cattle},
        )

    def test_export_separates_affected_values_from_prior_village_census(self):
        report = IncidentReport.objects.create(
            data={
                "animal_species": "Cattle",
                "num_household": 3,
                "num_total_animal": 10,
            },
            reported_by=self.jatujak_reporter,
            incident_date=date(2026, 3, 1),
            report_type=self.animal_sick_death_report_type,
            relevant_authority_resolved=True,
            village=self.village,
        )
        report.relevant_authorities.add(self.jatujak)
        case = Case.objects.create(
            report=report,
            is_finished=True,
            stopped_at=datetime(2026, 3, 20, tzinfo=timezone.utc),
            close_source=Case.CloseSource.SYSTEM,
        )
        report.case_id = case.id
        report.save(update_fields=["case_id", "updated_at"])

        rows = collect_export_rows(
            report_type=self.animal_sick_death_report_type
        )

        self.assertEqual(1, len(rows))
        row = rows[0]
        cattle = SPECIES_HEADERS.index("Cattle")
        self.assertEqual("Selected village", row[3])
        self.assertEqual(10, row[COL_POP_START - 1 + cattle])
        self.assertEqual(3, row[COL_AFFECTED_HOUSEHOLDS - 1])
        self.assertEqual(80, row[COL_VILLAGE_HOUSEHOLDS - 1])
        self.assertEqual(120, row[COL_VILLAGE_POP_START - 1 + cattle])
        self.assertEqual("System", row[COL_CLOSE_SOURCE - 1])
