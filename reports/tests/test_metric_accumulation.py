from django.test import SimpleTestCase, TestCase
from django.utils.timezone import now

from reports.metric_accumulation import (
    accumulate_incident_metrics,
    accumulate_metrics,
    extract_number,
    parse_metric_specs,
)
from reports.models import FollowUpReport, IncidentReport, ReportType
from reports.tests.base_testcase import BaseTestCase


class ExtractNumberTests(SimpleTestCase):
    def test_plain_int(self):
        self.assertEqual(extract_number({"num_sick": 3}, "num_sick"), 3)

    def test_string_number(self):
        self.assertEqual(extract_number({"num_sick": "4"}, "num_sick"), 4)

    def test_missing(self):
        self.assertIsNone(extract_number({}, "num_sick"))
        self.assertIsNone(extract_number(None, "num_sick"))

    def test_invalid(self):
        self.assertIsNone(extract_number({"num_sick": "x"}, "num_sick"))


class ParseSpecsTests(SimpleTestCase):
    def test_empty_config(self):
        self.assertEqual(parse_metric_specs(None), [])
        self.assertEqual(parse_metric_specs({}), [])
        self.assertEqual(parse_metric_specs({"metrics": "nope"}), [])

    def test_valid_specs(self):
        config = {
            "version": 1,
            "metrics": [
                {
                    "id": "num_sick",
                    "label": "Sick",
                    "reportField": "num_sick",
                    "followupField": "num_sick",
                    "op": "sum",
                }
            ],
        }
        specs = parse_metric_specs(config)
        self.assertEqual(len(specs), 1)
        self.assertEqual(specs[0]["op"], "sum")

    def test_skips_bad_op(self):
        config = {
            "metrics": [
                {
                    "id": "x",
                    "reportField": "x",
                    "op": "multiply",
                }
            ]
        }
        self.assertEqual(parse_metric_specs(config), [])


class AccumulateMetricsPureTests(SimpleTestCase):
    def _config(self, op="sum"):
        return {
            "version": 1,
            "metrics": [
                {
                    "id": "num_sick",
                    "label": "Sick",
                    "reportField": "num_sick",
                    "followupField": "num_sick",
                    "op": op,
                },
                {
                    "id": "num_dead",
                    "label": "Dead",
                    "reportField": "num_dead",
                    "followupField": "num_dead",
                    "op": op,
                },
            ],
        }

    def test_sum_report_plus_followups(self):
        result = accumulate_metrics(
            {"num_sick": 3, "num_dead": 1},
            [{"num_sick": 1}, {"num_sick": 2, "num_dead": 1}],
            self._config("sum"),
        )
        by_id = {m["id"]: m for m in result["metrics"]}
        self.assertEqual(by_id["num_sick"]["value"], 6)
        self.assertEqual(by_id["num_sick"]["reportValue"], 3)
        self.assertEqual(by_id["num_sick"]["followupValues"], [1, 2])
        self.assertEqual(by_id["num_dead"]["value"], 2)

    def test_sum_missing_as_zero(self):
        result = accumulate_metrics(
            {},
            [{}],
            self._config("sum"),
        )
        by_id = {m["id"]: m for m in result["metrics"]}
        self.assertEqual(by_id["num_sick"]["value"], 0)

    def test_latest_prefers_last_followup(self):
        result = accumulate_metrics(
            {"num_sick": 3},
            [{"num_sick": 1}, {"num_sick": 9}],
            self._config("latest"),
        )
        by_id = {m["id"]: m for m in result["metrics"]}
        self.assertEqual(by_id["num_sick"]["value"], 9)

    def test_latest_falls_back_to_report(self):
        result = accumulate_metrics(
            {"num_sick": 3},
            [{}, {}],
            self._config("latest"),
        )
        by_id = {m["id"]: m for m in result["metrics"]}
        self.assertEqual(by_id["num_sick"]["value"], 3)

    def test_positive_only_omits_unknown_or_nonpositive_total(self):
        config = self._config()
        config["metrics"][0]["positiveOnly"] = True
        for value in (None, "", 0, -1, "invalid"):
            with self.subTest(value=value):
                result = accumulate_metrics({"num_sick": value}, [{}], config)
                self.assertEqual([m["id"] for m in result["metrics"]], ["num_dead"])
                self.assertEqual(result["metrics"][0]["value"], 0)

    def test_positive_only_sum_keeps_positive_report_and_followups(self):
        config = self._config()
        config["metrics"][0]["positiveOnly"] = True
        result = accumulate_metrics(
            {"num_sick": 10},
            [{"num_sick": None}, {"num_sick": 0}, {"num_sick": -2}, {"num_sick": 5}],
            config,
        )
        self.assertEqual(result["metrics"][0]["value"], 15)
        self.assertEqual(result["metrics"][0]["reportValue"], 10)
        self.assertEqual(result["metrics"][0]["followupValues"], [0, 0, 0, 5])

    def test_positive_only_latest_keeps_last_known_positive(self):
        config = self._config("latest")
        config["metrics"][0]["positiveOnly"] = True
        result = accumulate_metrics(
            {"num_sick": 10}, [{"num_sick": 20}, {"num_sick": 0}, {}], config
        )
        self.assertEqual(result["metrics"][0]["value"], 20)

    def test_positive_only_can_start_from_a_followup(self):
        config = self._config()
        config["metrics"][0]["positiveOnly"] = True
        result = accumulate_metrics({}, [{"num_sick": 12}], config)
        self.assertEqual(result["metrics"][0]["value"], 12)

    def test_null_config_empty(self):
        result = accumulate_metrics({"num_sick": 1}, [{"num_sick": 1}], None)
        self.assertEqual(result["metrics"], [])


class AccumulateIncidentIntegrationTests(BaseTestCase):
    def test_incident_with_followups(self):
        self.mers_report_type.metric_accumulation = {
            "version": 1,
            "metrics": [
                {
                    "id": "num_sick",
                    "label": "Sick",
                    "reportField": "number_of_sick",
                    "followupField": "number_of_sick",
                    "op": "sum",
                }
            ],
        }
        self.mers_report_type.save()

        incident = IncidentReport.objects.create(
            data={"number_of_sick": 2},
            reported_by=self.user,
            incident_date=now(),
            report_type=self.mers_report_type,
        )
        FollowUpReport.objects.create(
            reported_by=self.user,
            report_type=self.mers_report_type,
            data={"number_of_sick": 1},
            incident=incident,
        )
        FollowUpReport.objects.create(
            reported_by=self.user,
            report_type=self.mers_report_type,
            data={"number_of_sick": 3},
            incident=incident,
        )

        result = accumulate_incident_metrics(incident)
        self.assertEqual(result["metrics"][0]["value"], 6)
