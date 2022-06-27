from graphql_jwt.testcases import JSONWebTokenTestCase

from reports.models.category import Category


class AdminCategoryTests(JSONWebTokenTestCase):
    def setUp(self):
        self.category1 = Category.objects.create(name="cat1", ordering=1)
        self.category2 = Category.objects.create(name="cat2", ordering=2)

    def test_simple_query(self):
        query = """
        query adminCategoryQuery {
            adminCategoryQuery {
                results {
                    id
                    name
                    ordering

                }
            }
        }
        """
        result = self.client.execute(query, {})
        self.assertEqual(len(result.data["adminCategoryQuery"]["results"]), 2)

    def test_query_with_name(self):
        query = """
        query adminCategoryQuery($name: String) {
            adminCategoryQuery(name: $name) {
                results {
                    id
                    name
                    ordering
                }
            }
        }
        """
        result = self.client.execute(query, {"name": "cat1"})
        self.assertEqual(len(result.data["adminCategoryQuery"]["results"]), 1)

    def test_create_with_error(self):
        mutation = """
        mutation adminCategoryCreate($name: String!, $ordering: Int!) {
            adminCategoryCreate(name: $name, ordering: $ordering) {
                result {
                  __typename
                  ... on AdminCategoryCreateSuccess {
                    id
                    name
                    ordering
                  }
                  ... on AdminCategoryCreateProblem {
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
                "name": "cat1",
                "ordering": 1,
            },
        )
        self.assertIsNotNone(result.data["adminCategoryCreate"]["result"])
        self.assertIsNotNone(result.data["adminCategoryCreate"]["result"]["fields"])
        self.assertEqual(
            result.data["adminCategoryCreate"]["result"]["fields"][0]["name"],
            "name",
        )

    def test_create_success(self):
        mutation = """
        mutation adminCategoryCreate($name: String!, $ordering: Int!) {
            adminCategoryCreate(name: $name, ordering: $ordering) {
                result {
                  __typename
                  ... on AdminCategoryCreateSuccess {
                    id
                    name
                    ordering
                  }
                  ... on AdminCategoryCreateProblem {
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
                "name": "cat3",
                "ordering": 3,
            },
        )
        self.assertIsNotNone(result.data["adminCategoryCreate"]["result"])
        self.assertIsNotNone(result.data["adminCategoryCreate"]["result"]["id"])
        self.assertEqual(result.data["adminCategoryCreate"]["result"]["name"], "cat3")

    def test_update_with_error(self):
        mutation = """
        mutation adminCategoryUpdate($id: ID!, $name: String!, $ordering: Int!) {
            adminCategoryUpdate(id: $id, name: $name, ordering: $ordering) {
                result {
                  __typename
                  ... on AdminCategoryUpdateSuccess {
                    id
                    name
                    ordering
                  }
                  ... on AdminCategoryUpdateProblem {
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
                "id": self.category1.id,
                "name": "cat2",
                "ordering": 1,
            },
        )
        self.assertIsNotNone(result.data["adminCategoryUpdate"]["result"])
        self.assertIsNotNone(result.data["adminCategoryUpdate"]["result"]["fields"])
        self.assertEqual(
            result.data["adminCategoryUpdate"]["result"]["fields"][0]["name"],
            "name",
        )

    def test_update_success(self):
        mutation = """
        mutation adminCategoryUpdate($id: ID!, $name: String!, $ordering: Int!) {
            adminCategoryUpdate(id: $id, name: $name, ordering: $ordering) {
                result {
                  __typename
                  ... on AdminCategoryUpdateSuccess {
                    id
                    name
                    ordering
                  }
                  ... on AdminCategoryUpdateProblem {
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
                "id": self.category1.id,
                "name": "cat3",
                "ordering": 1,
            },
        )

        self.assertIsNotNone(result.data["adminCategoryUpdate"]["result"])
        self.assertIsNotNone(result.data["adminCategoryUpdate"]["result"]["id"])
        self.assertEqual(result.data["adminCategoryUpdate"]["result"]["name"], "cat3")
