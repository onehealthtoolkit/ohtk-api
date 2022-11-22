from django.contrib.auth import get_user_model
from graphql_jwt.testcases import JSONWebTokenTestCase

from accounts.models import Authority, InvitationCode, AuthorityUser


class AdminInvitationCodeTests(JSONWebTokenTestCase):
    def setUp(self):
        self.authority = Authority.objects.create(name="test", code="1")
        self.InvitationCode1 = InvitationCode.objects.create(
            authority=self.authority, code="11112", role=AuthorityUser.Role.REPORTER
        )
        self.InvitationCode2 = InvitationCode.objects.create(
            authority=self.authority, code="234343", role=AuthorityUser.Role.ADMIN
        )

        self.user = get_user_model().objects.create(username="test", is_superuser=True)
        self.client.authenticate(self.user)

    def test_simple_query(self):
        query = """
        query adminInvitationCodeQuery {
            adminInvitationCodeQuery {
                results {
                    id
                    code
                }
            }
        }
        """
        result = self.client.execute(query, {})
        self.assertEqual(len(result.data["adminInvitationCodeQuery"]["results"]), 2)

    def test_query_with_role(self):
        query = """
        query adminInvitationCodeQuery($role: String) {
            adminInvitationCodeQuery(role_Contains: $role) {
                results {
                    id
                    code
                }
            }
        }
        """
        result = self.client.execute(query, {"role": "REP"})
        self.assertEqual(len(result.data["adminInvitationCodeQuery"]["results"]), 1)

    def test_create_with_error(self):
        mutation = """
        mutation adminInvitationCodeCreate($code: String!, $authorityId: Int!) {
            adminInvitationCodeCreate(code: $code, authorityId: $authorityId) {
                result {
                  __typename
                  ... on AdminInvitationCodeCreateSuccess {
                    id
                    code
                  }
                  ... on AdminInvitationCodeCreateProblem {
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
                "code": "11112",
                "authorityId": self.authority.id,
            },
        )
        self.assertIsNotNone(result.data["adminInvitationCodeCreate"]["result"])
        self.assertIsNotNone(
            result.data["adminInvitationCodeCreate"]["result"]["fields"]
        )
        self.assertEqual(
            result.data["adminInvitationCodeCreate"]["result"]["fields"][0]["name"],
            "code",
        )

    def test_create_success(self):
        mutation = """
        mutation adminInvitationCodeCreate($code: String!, $authorityId: Int!, $fromDate: DateTime!, $throughDate: DateTime!) {
            adminInvitationCodeCreate(code: $code, authorityId: $authorityId, fromDate: $fromDate, throughDate: $throughDate) {
                result {
                  __typename
                  ... on AdminInvitationCodeCreateSuccess {
                    id
                    code
                    fromDate
                    throughDate
                  }
                  ... on AdminInvitationCodeCreateProblem {
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
                "code": "11113",
                "authorityId": self.authority.id,
                "fromDate": "2022-06-21T00:00:00.000Z",
                "throughDate": "2022-06-22T00:00:00.000Z",
            },
        )
        self.assertIsNotNone(result.data["adminInvitationCodeCreate"]["result"])
        self.assertIsNotNone(result.data["adminInvitationCodeCreate"]["result"]["id"])
        self.assertEqual(
            result.data["adminInvitationCodeCreate"]["result"]["code"], "11113"
        )

    def test_update_with_error(self):
        mutation = """
        mutation adminInvitationCodeUpdate($id: ID!, $code: String!) {
            adminInvitationCodeUpdate(id: $id, code: $code) {
                result {
                  __typename
                  ... on AdminInvitationCodeUpdateSuccess {
                    invitationCode {
                        code
                        id
                    }
                  }
                  ... on AdminInvitationCodeUpdateProblem {
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
            mutation, {"id": self.InvitationCode2.id, "code": "11112"}
        )
        self.assertIsNotNone(result.data["adminInvitationCodeUpdate"]["result"])
        self.assertIsNotNone(
            result.data["adminInvitationCodeUpdate"]["result"]["fields"]
        )
        self.assertEqual(
            result.data["adminInvitationCodeUpdate"]["result"]["fields"][0]["name"],
            "code",
        )

    def test_update_success(self):
        mutation = """
        mutation adminInvitationCodeUpdate($id: ID!, $code: String!) {
            adminInvitationCodeUpdate(id: $id, code: $code) {
                result {
                  __typename
                  ... on AdminInvitationCodeUpdateSuccess {
                    invitationCode {
                        code
                        id
                    }
                  }
                  ... on AdminInvitationCodeUpdateProblem {
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
            mutation, {"id": self.InvitationCode2.id, "code": "11113"}
        )
        self.assertIsNotNone(result.data["adminInvitationCodeUpdate"]["result"])
        self.assertIsNotNone(
            result.data["adminInvitationCodeUpdate"]["result"]["invitationCode"]["id"]
        )
        self.assertEqual(
            result.data["adminInvitationCodeUpdate"]["result"]["invitationCode"][
                "code"
            ],
            "11113",
        )
