from graphql_jwt.testcases import JSONWebTokenTestCase

from accounts.models import Authority, AuthorityUser


class AdminAuthorityUserTests(JSONWebTokenTestCase):
    def setUp(self):
        self.authority = Authority.objects.create(name="test", code="1")
        self.authorityUser1 = AuthorityUser.objects.create(
            username="test", authority=self.authority
        )
        self.authorityUser2 = AuthorityUser.objects.create(
            username="another", authority=self.authority
        )

    def test_simple_query(self):
        query = """
        query adminAuthorityUserQuery {
            adminAuthorityUserQuery {
                results {
                    id
                    username
                    firstName

                }
            }
        }
        """
        result = self.client.execute(query, {})
        self.assertEqual(len(result.data["adminAuthorityUserQuery"]["results"]), 2)

    def test_query_with_username(self):
        query = """
        query adminAuthorityUserQuery($username: String) {
            adminAuthorityUserQuery(username: $username) {
                results {
                    id
                    username
                    firstName
                }
            }
        }
        """
        result = self.client.execute(query, {"username": "test"})
        self.assertEqual(len(result.data["adminAuthorityUserQuery"]["results"]), 1)

    def test_create_with_error(self):
        mutation = """
        mutation adminAuthorityUserCreate($authorityId: Int!, $username: String!, $password: String!, $firstName: String!, $lastName: String!, $email: String!, $telephone: String) {
            adminAuthorityUserCreate(authorityId: $authorityId, username: $username, password: $password, firstName: $firstName, lastName: $lastName, email: $email, telephone: $telephone) {
                result {
                  __typename
                  ... on AdminAuthorityUserCreateSuccess {
                    id
                    username
                    firstName
                  }
                  ... on AdminAuthorityUserCreateProblem {
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
                "authorityId": self.authority.id,
                "username": "test",
                "password": "passw",
                "firstName": "one",
                "lastName": "",
                "email": "test@test.com",
                "telephone": "22222",
            },
        )
        self.assertIsNotNone(result.data["adminAuthorityUserCreate"]["result"])
        self.assertIsNotNone(
            result.data["adminAuthorityUserCreate"]["result"]["fields"]
        )
        self.assertEqual(
            result.data["adminAuthorityUserCreate"]["result"]["fields"][0]["name"],
            "username",
        )

    def test_create_success(self):
        mutation = """
        mutation adminAuthorityUserCreate($authorityId: Int!, $username: String!, $password: String!, $firstName: String!, $lastName: String!, $email: String!, $telephone: String) {
            adminAuthorityUserCreate(authorityId: $authorityId, username: $username, password: $password, firstName: $firstName, lastName: $lastName, email: $email, telephone: $telephone) {
                result {
                  __typename
                  ... on AdminAuthorityUserCreateSuccess {
                    id
                    username
                    password
                    firstName
                  }
                  ... on AdminAuthorityUserCreateProblem {
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
                "authorityId": self.authority.id,
                "username": "test2",
                "password": "passw",
                "firstName": "Mr First",
                "lastName": "oooo",
                "email": "test@test.com",
                "telephone": "22222",
            },
        )
        self.assertIsNotNone(result.data["adminAuthorityUserCreate"]["result"])
        self.assertIsNotNone(result.data["adminAuthorityUserCreate"]["result"]["id"])
        self.assertEqual(
            result.data["adminAuthorityUserCreate"]["result"]["username"], "test2"
        )

    def test_update_with_error(self):
        mutation = """
        mutation adminAuthorityUserUpdate($id: ID!, $authorityId: Int!, $username: String!, $firstName: String!, $lastName: String!, $email: String!, $telephone: String) {
            adminAuthorityUserUpdate(id: $id,  authorityId: $authorityId, username: $username, firstName: $firstName, lastName: $lastName, email: $email, telephone: $telephone) {
                result {
                  __typename
                  ... on AdminAuthorityUserUpdateSuccess {
                    authorityUser {
                        id
                        username
                        firstName
                    }
                  }
                  ... on AdminAuthorityUserUpdateProblem {
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
                "id": self.authorityUser1.id,
                "authorityId": self.authority.id,
                "username": "another",
                "firstName": "Mr First",
                "lastName": "oooo",
                "email": "test@test.com",
                "telephone": "22222",
            },
        )
        self.assertIsNotNone(result.data["adminAuthorityUserUpdate"]["result"])
        self.assertIsNotNone(
            result.data["adminAuthorityUserUpdate"]["result"]["fields"]
        )
        self.assertEqual(
            result.data["adminAuthorityUserUpdate"]["result"]["fields"][0]["name"],
            "username",
        )

    def test_update_success(self):
        mutation = """
        mutation adminAuthorityUserUpdate($id: ID!, $authorityId: Int!, $username: String!, $firstName: String!, $lastName: String!, $email: String!, $telephone: String) {
            adminAuthorityUserUpdate(id: $id,  authorityId: $authorityId, username: $username, firstName: $firstName, lastName: $lastName, email: $email, telephone: $telephone) {
                result {
                  __typename
                  ... on AdminAuthorityUserUpdateSuccess {
                    authorityUser {
                        id
                        username
                        firstName
                    }
                  }
                  ... on AdminAuthorityUserUpdateProblem {
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
                "id": self.authorityUser1.id,
                "authorityId": self.authority.id,
                "username": "another3",
                "firstName": "Mr First",
                "lastName": "oooo",
                "email": "test@test.com",
                "telephone": "22222",
            },
        )

        self.assertIsNotNone(result.data["adminAuthorityUserUpdate"]["result"])
        self.assertIsNotNone(
            result.data["adminAuthorityUserUpdate"]["result"]["authorityUser"]["id"]
        )
        self.assertEqual(
            result.data["adminAuthorityUserUpdate"]["result"]["authorityUser"][
                "username"
            ],
            "another3",
        )
