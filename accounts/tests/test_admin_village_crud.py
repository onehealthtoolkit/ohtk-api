from django.contrib.gis.geos import Point
from graphql_jwt.testcases import JSONWebTokenTestCase

from accounts.models import Authority, AuthorityUser, User, Village
from accounts.village_capability import set_village_capability_enabled


class AdminVillageTests(JSONWebTokenTestCase):
    def setUp(self):
        self.super_user = User.objects.create(username="platform", is_superuser=True)
        self.authority = Authority.objects.create(name="test authority", code="TA")
        self.other_authority = Authority.objects.create(name="other authority", code="OA")
        self.village1 = Village.objects.create(
            code="V001",
            name="Village One",
            authority=self.authority,
            location=Point(100, 15),
        )
        self.village2 = Village.objects.create(
            code="V002",
            name="Village Two",
            authority=self.authority,
            active=False,
        )

    def execute_query(self, variables=None):
        query = """
        query adminVillageQuery($q: String, $active: Boolean) {
            adminVillageQuery(q: $q, active: $active) {
                results {
                    id
                    code
                    name
                    active
                    latitude
                    longitude
                    authority {
                        id
                        name
                    }
                }
            }
        }
        """
        return self.client.execute(query, variables or {})

    def execute_create(self, variables):
        mutation = """
        mutation adminVillageCreate(
            $code: String!,
            $name: String!,
            $authorityId: Int!,
            $latitude: Float,
            $longitude: Float,
            $active: Boolean
        ) {
            adminVillageCreate(
                code: $code,
                name: $name,
                authorityId: $authorityId,
                latitude: $latitude,
                longitude: $longitude,
                active: $active
            ) {
                result {
                    __typename
                    ... on AdminVillageCreateSuccess {
                        id
                        code
                        name
                        active
                        latitude
                        longitude
                    }
                    ... on AdminVillageCreateProblem {
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
        return self.client.execute(mutation, variables)

    def execute_update(self, variables):
        mutation = """
        mutation adminVillageUpdate(
            $id: Int!,
            $code: String!,
            $name: String!,
            $authorityId: Int!,
            $latitude: Float,
            $longitude: Float,
            $active: Boolean!
        ) {
            adminVillageUpdate(
                id: $id,
                code: $code,
                name: $name,
                authorityId: $authorityId,
                latitude: $latitude,
                longitude: $longitude,
                active: $active
            ) {
                result {
                    __typename
                    ... on AdminVillageUpdateSuccess {
                        id
                        code
                        name
                        active
                        latitude
                        longitude
                    }
                    ... on AdminVillageUpdateProblem {
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
        return self.client.execute(mutation, variables)

    def test_model_stores_village_under_authority(self):
        self.assertEqual(self.village1.authority, self.authority)
        self.assertEqual(self.village1.code, "V001")
        self.assertTrue(self.village1.active)
        self.assertEqual(self.village1.location.x, 100)
        self.assertEqual(self.village1.location.y, 15)

    def test_query_hides_villages_when_capability_disabled(self):
        self.client.authenticate(self.super_user)
        result = self.execute_query()
        self.assertIsNone(result.errors, result.errors)
        self.assertEqual(result.data["adminVillageQuery"]["results"], [])

    def test_query_lists_and_filters_villages_when_capability_enabled(self):
        set_village_capability_enabled(True)
        self.client.authenticate(self.super_user)
        result = self.execute_query({"q": "One", "active": True})
        self.assertIsNone(result.errors, result.errors)
        self.assertEqual(len(result.data["adminVillageQuery"]["results"]), 1)
        village = result.data["adminVillageQuery"]["results"][0]
        self.assertEqual(village["code"], "V001")
        self.assertEqual(village["latitude"], 15)
        self.assertEqual(village["longitude"], 100)

    def test_authority_admin_query_is_scoped_to_own_authority(self):
        set_village_capability_enabled(True)
        Village.objects.create(
            code="V999", name="Other Village", authority=self.other_authority
        )
        admin = AuthorityUser.objects.create(
            username="authority-admin",
            authority=self.authority,
            role=AuthorityUser.Role.ADMIN,
        )
        self.client.authenticate(admin)

        result = self.execute_query()

        self.assertIsNone(result.errors, result.errors)
        village_codes = [
            village["code"] for village in result.data["adminVillageQuery"]["results"]
        ]
        self.assertEqual(village_codes, ["V001", "V002"])

    def test_create_rejects_when_capability_disabled(self):
        self.client.authenticate(self.super_user)
        result = self.execute_create(
            {
                "code": "V003",
                "name": "Village Three",
                "authorityId": self.authority.id,
                "latitude": 16,
                "longitude": 101,
                "active": True,
            }
        )
        fields = result.data["adminVillageCreate"]["result"]["fields"]
        self.assertEqual(fields[0]["name"], "village_enabled")
        self.assertFalse(Village.objects.filter(code="V003").exists())

    def test_create_village_when_capability_enabled(self):
        set_village_capability_enabled(True)
        self.client.authenticate(self.super_user)
        result = self.execute_create(
            {
                "code": "V003",
                "name": "Village Three",
                "authorityId": self.authority.id,
                "latitude": 16,
                "longitude": 101,
                "active": True,
            }
        )
        self.assertIsNone(result.errors, result.errors)
        village = result.data["adminVillageCreate"]["result"]
        self.assertEqual(village["__typename"], "AdminVillageCreateSuccess")
        self.assertEqual(village["code"], "V003")
        self.assertEqual(village["latitude"], 16)
        self.assertEqual(village["longitude"], 101)
        self.assertTrue(Village.objects.filter(code="V003").exists())

    def test_create_rejects_unknown_authority(self):
        set_village_capability_enabled(True)
        self.client.authenticate(self.super_user)
        result = self.execute_create(
            {
                "code": "V003",
                "name": "Village Three",
                "authorityId": 999999,
                "active": True,
            }
        )
        fields = result.data["adminVillageCreate"]["result"]["fields"]
        self.assertEqual(fields[0]["name"], "authority_id")
        self.assertFalse(Village.objects.filter(code="V003").exists())

    def test_update_rejects_when_capability_disabled(self):
        self.client.authenticate(self.super_user)
        result = self.execute_update(
            {
                "id": self.village1.id,
                "code": "V001A",
                "name": "Village One Updated",
                "authorityId": self.authority.id,
                "active": False,
            }
        )
        fields = result.data["adminVillageUpdate"]["result"]["fields"]
        self.assertEqual(fields[0]["name"], "village_enabled")

        self.village1.refresh_from_db()
        self.assertEqual(self.village1.code, "V001")
        self.assertTrue(self.village1.active)

    def test_update_village_when_capability_enabled(self):
        set_village_capability_enabled(True)
        self.client.authenticate(self.super_user)
        result = self.execute_update(
            {
                "id": self.village1.id,
                "code": "V001A",
                "name": "Village One Updated",
                "authorityId": self.authority.id,
                "latitude": 17,
                "longitude": 102,
                "active": False,
            }
        )
        self.assertIsNone(result.errors, result.errors)
        village = result.data["adminVillageUpdate"]["result"]
        self.assertEqual(village["__typename"], "AdminVillageUpdateSuccess")
        self.assertEqual(village["code"], "V001A")
        self.assertFalse(village["active"])

        self.village1.refresh_from_db()
        self.assertEqual(self.village1.name, "Village One Updated")
        self.assertFalse(self.village1.active)

    def test_admin_cannot_create_village_outside_authority_scope(self):
        set_village_capability_enabled(True)
        admin = AuthorityUser.objects.create(
            username="authority-admin",
            authority=self.authority,
            role=AuthorityUser.Role.ADMIN,
        )
        self.client.authenticate(admin)
        result = self.execute_create(
            {
                "code": "V004",
                "name": "Village Four",
                "authorityId": self.other_authority.id,
                "active": True,
            }
        )
        fields = result.data["adminVillageCreate"]["result"]["fields"]
        self.assertEqual(fields[0]["name"], "authority_id")
        self.assertFalse(Village.objects.filter(code="V004").exists())
