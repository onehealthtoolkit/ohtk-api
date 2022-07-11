from graphql_jwt.testcases import JSONWebTokenTestCase

from accounts.models import Authority

area_geojson = """
        {
        "type": "Polygon",
        "coordinates": [
          [
            [
              43.9453125,
              22.268764039073968
            ],
            [
              41.1328125,
              27.059125784374068
            ],
            [
              33.046875,
              22.917922936146045
            ],
            [
              36.2109375,
              15.961329081596647
            ],
            [
              43.9453125,
              22.268764039073968
            ]
          ]
        ]
      }
      """


class AdminAuthorityTests(JSONWebTokenTestCase):
    def setUp(self):
        self.authority1 = Authority.objects.create(name="test", code="1")
        self.authority2 = Authority.objects.create(name="another", code="2")

    def test_simple_query(self):
        query = """
        query adminAuthorityQuery {
            adminAuthorityQuery {
                results {
                    id
                    code
                    name

                }
            }
        }
        """
        result = self.client.execute(query, {})
        self.assertEqual(len(result.data["adminAuthorityQuery"]["results"]), 2)

    def test_query_with_name(self):
        query = """
        query adminAuthorityQuery($name: String) {
            adminAuthorityQuery(name: $name) {
                results {
                    id
                    code
                    name
                }
            }
        }
        """
        result = self.client.execute(query, {"name": "test"})
        self.assertEqual(len(result.data["adminAuthorityQuery"]["results"]), 1)

    def test_create_with_error(self):
        mutation = """
        mutation adminAuthorityCreate($code: String!, $name: String!) {
            adminAuthorityCreate(code: $code, name: $name) {
                result {
                  __typename
                  ... on AdminAuthorityCreateSuccess {
                    name
                    id
                    createdAt
                  }
                  ... on AdminAuthorityCreateProblem {
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
        result = self.client.execute(mutation, {"code": "1", "name": "one"})
        self.assertIsNotNone(result.data["adminAuthorityCreate"]["result"])
        self.assertIsNotNone(result.data["adminAuthorityCreate"]["result"]["fields"])
        self.assertEqual(
            result.data["adminAuthorityCreate"]["result"]["fields"][0]["name"], "code"
        )

    def test_create_success(self):
        mutation = """
        mutation adminAuthorityCreate($code: String!, $name: String!) {
            adminAuthorityCreate(code: $code, name: $name) {
                result {
                  __typename
                  ... on AdminAuthorityCreateSuccess {
                    name
                    id
                    code
                    createdAt
                  }
                  ... on AdminAuthorityCreateProblem {
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
        result = self.client.execute(mutation, {"code": "99", "name": "any thing"})
        self.assertIsNotNone(result.data["adminAuthorityCreate"]["result"])
        self.assertIsNotNone(result.data["adminAuthorityCreate"]["result"]["id"])
        self.assertEqual(result.data["adminAuthorityCreate"]["result"]["code"], "99")

    def test_update_with_error(self):
        mutation = """
        mutation adminAuthorityUpdate($id: ID!, $code: String!, $name: String!) {
            adminAuthorityUpdate(id: $id, code: $code, name: $name) {
                result {
                  __typename
                  ... on AdminAuthorityUpdateSuccess {
                    authority {
                        name
                        id
                        code
                    }
                  }
                  ... on AdminAuthorityUpdateProblem {
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
            mutation, {"id": self.authority1.id, "code": "2", "name": "one"}
        )
        self.assertIsNotNone(result.data["adminAuthorityUpdate"]["result"])
        self.assertIsNotNone(result.data["adminAuthorityUpdate"]["result"]["fields"])
        self.assertEqual(
            result.data["adminAuthorityUpdate"]["result"]["fields"][0]["name"], "code"
        )

    def test_update_success(self):
        mutation = """
        mutation adminAuthorityUpdate($id: ID!, $code: String!, $name: String!) {
            adminAuthorityUpdate(id: $id, code: $code, name: $name) {
                result {
                  __typename
                  ... on AdminAuthorityUpdateSuccess {
                    authority {
                        name
                        id
                        code
                    }
                    
                  }
                  ... on AdminAuthorityUpdateProblem {
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
            mutation, {"id": self.authority1.id, "code": "99", "name": "any thing"}
        )
        self.assertIsNotNone(result.data["adminAuthorityUpdate"]["result"])
        self.assertIsNotNone(
            result.data["adminAuthorityUpdate"]["result"]["authority"]["id"]
        )
        self.assertEqual(
            result.data["adminAuthorityUpdate"]["result"]["authority"]["code"], "99"
        )

    def test_create_with_area_field(self):
        mutation = """
        mutation adminAuthorityCreate($code: String!, $name: String!, $area: String) {
            adminAuthorityCreate(code: $code, name: $name, area: $area) {
                result {
                  __typename
                  ... on AdminAuthorityCreateSuccess {
                    name
                    id
                    code                
                    area
                    createdAt
                  }
                  ... on AdminAuthorityCreateProblem {
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
            mutation, {"code": "99", "name": "any thing", "area": area_geojson}
        )
        self.assertIsNotNone(result.data["adminAuthorityCreate"]["result"])
        self.assertIsNotNone(result.data["adminAuthorityCreate"]["result"]["id"])
        self.assertEqual(result.data["adminAuthorityCreate"]["result"]["code"], "99")
        self.assertIsNotNone(result.data["adminAuthorityCreate"]["result"]["area"])

    def test_update_with_area_field_success(self):
        mutation = """
        mutation adminAuthorityUpdate($id: ID!, $code: String!, $name: String!, $area: String) {
            adminAuthorityUpdate(id: $id, code: $code, name: $name, area: $area) {
                result {
                  __typename
                  ... on AdminAuthorityUpdateSuccess {
                    authority {
                        name
                        id
                        code
                        area
                    }

                  }
                  ... on AdminAuthorityUpdateProblem {
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
                "id": self.authority1.id,
                "code": "99",
                "name": "any thing",
                "area": area_geojson,
            },
        )
        self.assertIsNotNone(result.data["adminAuthorityUpdate"]["result"])
        self.assertIsNotNone(
            result.data["adminAuthorityUpdate"]["result"]["authority"]["id"]
        )
        self.assertIsNotNone(
            result.data["adminAuthorityUpdate"]["result"]["authority"]["area"]
        )
        self.assertIsNotNone(
            result.data["adminAuthorityUpdate"]["result"]["authority"]["area"]["type"]
        )
        self.assertEqual(
            result.data["adminAuthorityUpdate"]["result"]["authority"]["area"]["type"],
            "Polygon",
        )
        self.assertIsNotNone(
            result.data["adminAuthorityUpdate"]["result"]["authority"]["area"][
                "coordinates"
            ]
        )
        self.assertEqual(
            result.data["adminAuthorityUpdate"]["result"]["authority"]["code"], "99"
        )
