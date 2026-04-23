import json

from django.conf import settings
from django.test import TestCase

from accounts.models import Authority, InvitationCode, User, Configuration
from accounts.utils import domain


class InvitationCodeTestCase(TestCase):
    graphql_url = "/graphql/"

    def setUp(self):
        self.authority = Authority.objects.create(
            code="A1",
            name="A1 name",
        )
        self.invitationCode = InvitationCode.objects.create(
            code="1234",
            authority=self.authority,
        )
        self.existingUser = User.objects.create(
            username="polawat",
            first_name="polawat",
            last_name="phetra",
            email="pphetra@mail.com",
        )
        self.check_query = """
            query checkInvitationCode($code: String!) {
              checkInvitationCode(code: $code) {
                code
                authority {
                  code
                  name
                }
                generatedUsername
                generatedEmail
              }
            }
            """
        self.register_mutation = """
            mutation authorityUserRegister($username: String!, $invitationCode: String!, $firstName: String!, $lastName: String!, $email: String!) {
                authorityUserRegister(username: $username, invitationCode: $invitationCode, firstName: $firstName, lastName: $lastName, email: $email) {
                    me {
                        id
                        username
                    }
                    token
                    refreshToken
                }
            
            }
        """

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

    def assertGraphQLHasErrors(self, response):
        self.assertIn(response.status_code, (200, 400), response.content)
        content = json.loads(response.content)
        self.assertIn("errors", content, content)
        return content

    def test_create(self):
        invitation = InvitationCode.objects.create(authority=self.authority)
        self.assertIsNotNone(invitation.code)
        self.assertIsNotNone(invitation.from_date)
        self.assertIsNotNone(invitation.through_date)

    def test_check_query_does_not_exist(self):
        response = self.graphql_query(self.check_query, variables={"code": "7777"})
        self.assertGraphQLHasErrors(response)

    def test_check_query_success(self):
        response = self.graphql_query(
            self.check_query,
            variables={"code": self.invitationCode.code},
        )
        content = self.assertGraphQLNoErrors(response)
        self.assertEqual(
            self.invitationCode.code, content["data"]["checkInvitationCode"]["code"]
        )
        self.assertEqual(
            self.authority.code,
            content["data"]["checkInvitationCode"]["authority"]["code"],
        )

    def test_check_query_with_auto_generated_username(self):
        Configuration.objects.create(
            key="features.auto_generate_username",
            value="enable",
        )
        response = self.graphql_query(
            self.check_query,
            variables={"code": self.invitationCode.code},
        )
        content = self.assertGraphQLNoErrors(response)
        self.assertIsNotNone(
            content["data"]["checkInvitationCode"]["generatedUsername"],
        )
        self.assertIsNone(
            content["data"]["checkInvitationCode"]["generatedEmail"],
        )

    def test_check_query_with_auto_generated_email(self):
        Configuration.objects.create(
            key="features.auto_generate_email",
            value="enable",
        )
        response = self.graphql_query(
            self.check_query,
            variables={"code": self.invitationCode.code},
        )
        content = self.assertGraphQLNoErrors(response)
        self.assertIsNotNone(
            content["data"]["checkInvitationCode"]["generatedEmail"],
        )
        self.assertIsNone(
            content["data"]["checkInvitationCode"]["generatedUsername"],
        )

    def test_check_query_with_auto_generated_username_and_email(self):
        Configuration.objects.create(
            key="features.auto_generate_username",
            value="enable",
        )
        Configuration.objects.create(
            key="features.auto_generate_email",
            value="enable",
        )
        response = self.graphql_query(
            self.check_query,
            variables={"code": self.invitationCode.code},
        )
        content = self.assertGraphQLNoErrors(response)
        generated_username = content["data"]["checkInvitationCode"]["generatedUsername"]

        self.assertIsNotNone(generated_username)
        self.assertEqual(
            content["data"]["checkInvitationCode"]["generatedEmail"],
            f"{generated_username}@generated.ohtk.org",
        )

    def test_user_registration_via_code(self):
        settings.AUTO_LOGIN_AFTER_REGISTER = False
        response = self.graphql_query(
            self.register_mutation,
            variables={
                "username": "pphetra",
                "invitationCode": "1234",
                "firstName": "john",
                "lastName": "Doe",
                "email": "pphetra@gmail.com",
            },
        )
        self.assertGraphQLNoErrors(response)

    def test_user_registration_via_code_and_auto_login(self):
        settings.AUTO_LOGIN_AFTER_REGISTER = True
        response = self.graphql_query(
            self.register_mutation,
            variables={
                "username": "pphetra",
                "invitationCode": "1234",
                "firstName": "john",
                "lastName": "Doe",
                "email": "pphetra@gmail.com",
            },
        )
        content = self.assertGraphQLNoErrors(response)
        payload = content["data"]["authorityUserRegister"]
        self.assertIsNotNone(payload["token"])
        self.assertIsNotNone(payload["refreshToken"])

    def test_user_registration_with_duplicate_username(self):
        settings.AUTO_LOGIN_AFTER_REGISTER = False
        response = self.graphql_query(
            self.register_mutation,
            variables={
                "username": "polawat",
                "invitationCode": "1234",
                "firstName": "john",
                "lastName": "Doe",
                "email": "pphetra@gmail.com",
            },
        )
        self.assertGraphQLHasErrors(response)
