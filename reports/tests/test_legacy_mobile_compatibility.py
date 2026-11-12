"""Keep actual unchanged mobile baseline operations valid on the new API."""
import json
from pathlib import Path

from django.test import SimpleTestCase
from graphql import parse, validate

from podd_api.schema import schema


class LegacyMobileSchemaTests(SimpleTestCase):
    def test_all_baseline_mobile_graphql_operations_remain_valid(self):
        fixture = json.loads(
            (Path(__file__).parent / "fixtures/mobile_graphql_8d0409c.json").read_text()
        )
        self.assertEqual(48, len(fixture["operations"]))
        for operation in fixture["operations"]:
            with self.subTest(path=operation["path"], line=operation["line"]):
                errors = validate(schema.graphql_schema, parse(operation["document"]))
                self.assertEqual([], [error.message for error in errors])
