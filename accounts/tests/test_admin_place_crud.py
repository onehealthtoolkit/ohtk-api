from django.contrib.gis.geos import Point
from graphql_jwt.testcases import JSONWebTokenTestCase

from accounts.models import User, Authority, Place


class AdminPlaceTests(JSONWebTokenTestCase):
    def setUp(self):
        self.super_user = User.objects.create(username="admintest", is_superuser=True)
        self.client.authenticate(self.super_user)
        self.authority = Authority.objects.create(name="test authority")
        self.place1 = Place.objects.create(
            name="place1", authority=self.authority, location=Point(1, 1)
        )
        self.place2 = Place.objects.create(
            name="place2", authority=self.authority, location=Point(2, 2)
        )

    def test_simple_query(self):
        query = """
        query adminPlaceQuery {
            adminPlaceQuery {
                results {
                    id
                    name
                    notificationTo
                    authority {
                        id
                        name
                    }
                }
            }
        }
        """
        result = self.client.execute(query, {})
        self.assertEqual(len(result.data["adminPlaceQuery"]["results"]), 2)

    def test_filter_query(self):
        query = """
        query adminPlaceQuery($q: String) {
            adminPlaceQuery(q: $q) {
                results {
                    id
                    name
                    notificationTo
                    authority {
                        id
                        name
                    }
                }
            }
        }
        """
        result = self.client.execute(query, {"q": "place1"})
        self.assertEqual(len(result.data["adminPlaceQuery"]["results"]), 1)

    def test_create(self):
        mutation = """
        mutation adminPlaceCreate($name: String!, $authorityId: Int!, $latitude: Float!, $longitude: Float!, $notificationTo: String) {
            adminPlaceCreate(name: $name, authorityId: $authorityId, latitude: $latitude, longitude: $longitude, notificationTo: $notificationTo) {
                result {
                    __typename
                    ... on AdminPlaceCreateSuccess {
                        id
                        name
                    }
                    ... on AdminPlaceCreateProblem {
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
                "name": "place3",
                "authorityId": self.authority.id,
                "latitude": 3,
                "longitude": 3,
            },
        )
        self.assertIsNotNone(result.data["adminPlaceCreate"]["result"])
        self.assertIsNotNone(result.data["adminPlaceCreate"]["result"]["id"])

    def test_update(self):
        mutation = """
        mutation adminPlaceUpdate($id: Int!, $name: String!, $authorityId: Int!, $latitude: Float!, $longitude: Float!,
            $notificationTo: String) {
            adminPlaceUpdate(id: $id, name: $name, authorityId: $authorityId, latitude: $latitude, 
                longitude: $longitude, notificationTo: $notificationTo) {
                result {
                    __typename
                    ... on AdminPlaceUpdateSuccess {
                        id
                        name
                    }
                    ... on AdminPlaceUpdateProblem {
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
                "id": self.place1.id,
                "name": "place3",
                "authorityId": self.authority.id,
                "latitude": 3,
                "longitude": 3,
                "notificationTo": "email:pphetra@gmail.com",
            },
        )
        print(result)
        self.assertIsNotNone(result.data["adminPlaceUpdate"]["result"])
        self.assertIsNotNone(result.data["adminPlaceUpdate"]["result"]["id"])
        self.place1.refresh_from_db()
        self.assertEqual(self.place1.name, "place3")

    def test_delete(self):
        mutation = """
        mutation adminPlaceDelete($id: Int!) {
            adminPlaceDelete(id: $id) {
                success
            }
        }
        """
        result = self.client.execute(mutation, {"id": self.place1.id})
        print(result)
        self.assertIsNotNone(result.data["adminPlaceDelete"]["success"])
        self.assertTrue(result.data["adminPlaceDelete"]["success"])
        self.assertEqual(Place.objects.count(), 1)
