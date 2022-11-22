from graphql_jwt.testcases import JSONWebTokenTestCase
from django.test.utils import override_settings
from django.contrib.auth import get_user_model


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
