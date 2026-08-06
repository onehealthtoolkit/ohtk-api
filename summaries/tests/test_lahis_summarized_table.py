from datetime import datetime, timezone

from django.test import SimpleTestCase

from summaries.lahis_summarized_table import (
    COL_DEAD_START,
    COL_POP_START,
    COL_SICK_START,
    COL_STAMP_START,
    COL_RECOVER_START,
    SPECIES_HEADERS,
    build_row_values,
    build_workbook,
    normalize_species,
    parse_gps,
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

    def test_build_row_places_metrics_only_on_report_species(self):
        row = build_row_values(
            report_id=42,
            data={
                "animal_species": "Cattle",
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
        )
        self.assertEqual(40, len(row))
        self.assertEqual("42", row[0])
        self.assertEqual("Vientiane Capital", row[1])
        self.assertEqual("Sangthong", row[2])
        self.assertEqual("Ban Sangthong", row[3])
        self.assertEqual("17.97000", row[4])  # latitude
        self.assertEqual("102.60000", row[5])  # longitude
        self.assertEqual("FMD", row[8])
        self.assertEqual("lab negative", row[9])

        cattle = SPECIES_HEADERS.index("Cattle")
        # Cattle filled
        self.assertEqual(10, row[COL_POP_START - 1 + cattle])
        self.assertEqual(3, row[COL_SICK_START - 1 + cattle])
        self.assertEqual(1, row[COL_DEAD_START - 1 + cattle])
        self.assertEqual(2, row[COL_RECOVER_START - 1 + cattle])
        self.assertEqual(4, row[COL_STAMP_START - 1 + cattle])
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
        self.assertEqual("Longitude", ws.cell(3, 6).value)
        self.assertEqual("suspected", ws.cell(3, 9).value)
        self.assertEqual("Cattle", ws.cell(3, COL_POP_START + species_column_offset("Cattle")).value)
