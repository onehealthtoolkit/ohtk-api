from graphql_jwt.testcases import JSONWebTokenTestCase
from django.test.utils import override_settings
from django.contrib.auth import get_user_model

from accounts.models import Authority, AuthorityUser


class AdminUserUpdateProfileTests(JSONWebTokenTestCase):
    def setUp(self):
        self.user = get_user_model().objects.create(username="test")
        self.client.authenticate(self.user)

    @override_settings(DEBUG=True)
    def test_update_profile(self):
        query = """
        mutation adminUserUpdateProfile($firstName: String!,$lastName: String!,$telephone: String) {
            adminUserUpdateProfile(firstName: $firstName,lastName: $lastName,telephone: $telephone
            ) {
                success
            }        
        }
        """
        result = self.client.execute(
            query, variables={"firstName": "first_name", "lastName": "last_mame"}
        )
        self.assertTrue(result.data["adminUserUpdateProfile"]["success"])

        query = """
        query me {
            me {
                id
                firstName
                lastName
            }
        }
        """
        result = self.client.execute(query, {})
        self.assertEqual("first_name", result.data["me"]["firstName"])
        self.assertEqual("last_mame", result.data["me"]["lastName"])

    @override_settings(DEBUG=True)
    def test_update_profile_gender_and_age(self):
        authority = Authority.objects.create(code="A1", name="Auth")
        user = AuthorityUser.objects.create(
            username="reporter1",
            authority=authority,
            role=AuthorityUser.Role.REPORTER,
            first_name="Old",
            last_name="Name",
        )
        self.client.authenticate(user)

        mutation = """
        mutation adminUserUpdateProfile(
          $firstName: String!
          $lastName: String!
          $telephone: String
          $address: String
          $gender: String
          $age: Int
        ) {
          adminUserUpdateProfile(
            firstName: $firstName
            lastName: $lastName
            telephone: $telephone
            address: $address
            gender: $gender
            age: $age
          ) {
            success
          }
        }
        """
        result = self.client.execute(
            mutation,
            variables={
                "firstName": "New",
                "lastName": "Reporter",
                "telephone": "0800000000",
                "address": "Village 1",
                "gender": "female",
                "age": 28,
            },
        )
        self.assertIsNone(result.errors)
        self.assertTrue(result.data["adminUserUpdateProfile"]["success"])

        user.refresh_from_db()
        self.assertEqual(user.first_name, "New")
        self.assertEqual(user.last_name, "Reporter")
        self.assertEqual(user.gender, "female")
        self.assertEqual(user.age, 28)

        me_query = """
        query me {
          me {
            gender
            age
          }
        }
        """
        me = self.client.execute(me_query, {})
        self.assertEqual(me.data["me"]["gender"], "female")
        self.assertEqual(me.data["me"]["age"], 28)
