import json

from django.contrib.auth import get_user_model
from django.test import TestCase


class JWTCookieTests(TestCase):
    graphql_url = "/graphql/"
    token_auth_mutation = """
        mutation TokenAuth($username: String!, $password: String!) {
            tokenAuth(username: $username, password: $password) {
                token
                refreshToken
            }
        }
    """

    delete_cookie_mutation = """
        mutation DeleteJwtCookies {
            deleteTokenCookie {
                deleted
            }
            deleteRefreshTokenCookie {
                deleted
            }
        }
    """

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="cookie-user",
            password="s3cret-pass",
        )

    def graphql_query(self, query, variables=None):
        body = {"query": query}
        if variables:
            body["variables"] = variables
        return self.client.post(
            self.graphql_url,
            data=json.dumps(body),
            content_type="application/json",
        )

    def assertGraphQLNoErrors(self, response):
        self.assertEqual(response.status_code, 200, response.content)
        content = json.loads(response.content)
        self.assertNotIn("errors", content, content)
        return content

    def test_delete_cookie_keeps_samesite_for_cross_site_jwt_cookies(self):
        login_response = self.graphql_query(
            self.token_auth_mutation,
            variables={
                "username": self.user.username,
                "password": "s3cret-pass",
            },
        )
        login_content = self.assertGraphQLNoErrors(login_response)

        login_payload = login_content["data"]["tokenAuth"]
        self.assertIsNotNone(login_payload["token"])
        self.assertIsNotNone(login_payload["refreshToken"])
        self.assertEqual("None", login_response.cookies["JWT"]["samesite"])
        self.assertEqual(
            "None",
            login_response.cookies["JWT-refresh-token"]["samesite"],
        )

        delete_response = self.graphql_query(self.delete_cookie_mutation)
        delete_content = self.assertGraphQLNoErrors(delete_response)

        delete_payload = delete_content["data"]
        self.assertTrue(delete_payload["deleteTokenCookie"]["deleted"])
        self.assertTrue(delete_payload["deleteRefreshTokenCookie"]["deleted"])
        self.assertEqual("None", delete_response.cookies["JWT"]["samesite"])
        self.assertEqual(
            "None",
            delete_response.cookies["JWT-refresh-token"]["samesite"],
        )
        self.assertTrue(delete_response.cookies["JWT"]["secure"])
        self.assertTrue(delete_response.cookies["JWT-refresh-token"]["secure"])
