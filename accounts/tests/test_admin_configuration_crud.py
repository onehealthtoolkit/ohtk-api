from django.contrib.gis.geos import Point
from graphql_jwt.testcases import JSONWebTokenTestCase

from accounts.models import User, Authority, Configuration


class AdminConfigurationTests(JSONWebTokenTestCase):
    def setUp(self):
        self.super_user = User.objects.create(username="admintest", is_superuser=True)
        self.client.authenticate(self.super_user)
        self.authority = Authority.objects.create(name="test authority")
        self.configuration1 = Configuration.objects.create(
            key="configuration1", value="configuration value1"
        )
        self.configuration2 = Configuration.objects.create(
            key="configuration2", value="configuration value2"
        )

    def test_simple_query(self):
        query = """
        query adminConfigurationQuery {
            adminConfigurationQuery {
                results {
                    key
                    value
                }
            }
        }
        """
        result = self.client.execute(query, {})
        self.assertEqual(len(result.data["adminConfigurationQuery"]["results"]), 2)

    def test_filter_query(self):
        query = """
        query adminConfigurationQuery($q: String) {
            adminConfigurationQuery(q: $q) {
                results {
                    key
                    value
                }
            }
        }
        """
        result = self.client.execute(query, {"q": "configuration1"})
        self.assertEqual(len(result.data["adminConfigurationQuery"]["results"]), 1)

    def test_create(self):
        mutation = """
        mutation adminConfigurationCreate($key: String!, $value: String!) {
            adminConfigurationCreate(key: $key, value: $value) {
                result {
                    __typename
                    ... on AdminConfigurationCreateSuccess {
                        key
                        value
                    }
                    ... on AdminConfigurationCreateProblem {
                        message
                        fields {
                            name
                            message
                        }
                    }
                }
            }
        }
        """
        result = self.client.execute(
            mutation,
            {
                "key": "configuration3",
                "value": "configuration value3",
            },
        )
        self.assertIsNotNone(result.data["adminConfigurationCreate"]["result"])
        self.assertIsNotNone(result.data["adminConfigurationCreate"]["result"]["key"])

    def test_update(self):
        mutation = """
        mutation adminConfigurationUpdate($id: String!, $key: String!, $value: String!) {
            adminConfigurationUpdate(id: $id, key: $key, value: $value) {
                result {
                    __typename
                    ... on AdminConfigurationUpdateSuccess {
                        key
                        value
                    }
                    ... on AdminConfigurationUpdateProblem {
                        message
                        fields {
                            name
                            message
                        }
                    }
                }
            }
        }
        """
        result = self.client.execute(
            mutation,
            {
                "id": self.configuration1.key,
                "key": self.configuration1.key,
                "value": "configuration value3",
            },
        )
        print(result)
        self.assertIsNotNone(result.data["adminConfigurationUpdate"]["result"])
        self.assertIsNotNone(result.data["adminConfigurationUpdate"]["result"]["key"])
        self.configuration1.refresh_from_db()
        self.assertEqual(self.configuration1.value, "configuration value3")

    def test_delete(self):
        mutation = """
        mutation adminConfigurationDelete($id: String!) {
            adminConfigurationDelete(id: $id) {
                success
            }
        }
        """
        result = self.client.execute(mutation, {"id": self.configuration1.key})
        print(result)
        self.assertIsNotNone(result.data["adminConfigurationDelete"]["success"])
        self.assertTrue(result.data["adminConfigurationDelete"]["success"])
        self.assertEqual(Configuration.objects.count(), 1)
