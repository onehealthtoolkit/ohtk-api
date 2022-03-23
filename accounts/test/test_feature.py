from django.test import TestCase
from graphql_jwt.testcases import JSONWebTokenClient

from accounts.models import Feature


class FeatureTestCase(TestCase):
    client_class = JSONWebTokenClient

    def setUp(self):
        self.feature1 = Feature.objects.create(
            key="anonymous_allow",
            value="true",
        )
        self.feature2 = Feature.objects.create(
            key="report_with_custom_location",
            value="true",
        )

    def test_query(self):
        query = """
                query features {
                    features {
                        key
                        value
                    }
                }
                """
        result = self.client.execute(query, {})
        self.assertIsNone(result.errors, result.errors)
        self.assertEqual(2, len(result.data["features"]))
