import json

from django.conf import settings
from graphene_django.utils import GraphQLTestCase

from accounts.models import Authority, InvitationCode, Domain, User
from accounts.utils import domain


class InvitationCodeTestCase(GraphQLTestCase):
    def setUp(self):
        self.domain = Domain.objects.create(code="domain1")
        self.authority = Authority.objects.create(
            code="A1", name="A1 name", domain=self.domain
        )
        self.invitationCode = InvitationCode.objects.create(
            code="1234", authority=self.authority, domain=self.domain
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

    def test_create(self):
        with domain(self.domain.id):
            invitation = InvitationCode.objects.create(authority=self.authority)
            self.assertIsNotNone(invitation.code)
            self.assertIsNotNone(invitation.from_date)
            self.assertIsNotNone(invitation.through_date)

    def test_check_query_does_not_exist(self):
        response = self.query(self.check_query, variables={"code": "7777"})
        self.assertResponseHasErrors(response)

    def test_check_query_success(self):
        with domain(self.domain.id):
            response = self.query(
                self.check_query,
                variables={"code": self.invitationCode.code},
            )
            self.assertResponseNoErrors(response)
            content = json.loads(response.content)
            self.assertEqual(
                self.invitationCode.code, content["data"]["checkInvitationCode"]["code"]
            )
            self.assertEqual(
                self.authority.code,
                content["data"]["checkInvitationCode"]["authority"]["code"],
            )

    def test_user_registration_via_code(self):
        settings.AUTO_LOGIN_AFTER_REGISTER = False
        with domain(self.domain.id):
            response = self.query(
                self.register_mutation,
                variables={
                    "username": "pphetra",
                    "invitationCode": "1234",
                    "firstName": "john",
                    "lastName": "Doe",
                    "email": "pphetra@gmail.com",
                },
            )
            self.assertResponseNoErrors(response)

    def test_user_registration_via_code_and_auto_login(self):
        settings.AUTO_LOGIN_AFTER_REGISTER = True
        with domain(self.domain.id):
            response = self.query(
                self.register_mutation,
                variables={
                    "username": "pphetra",
                    "invitationCode": "1234",
                    "firstName": "john",
                    "lastName": "Doe",
                    "email": "pphetra@gmail.com",
                },
            )
            self.assertResponseNoErrors(response)
            print(response)
            content = json.loads(response.content)
            payload = content["data"]["authorityUserRegister"]
            self.assertIsNotNone(payload["token"])
            self.assertIsNotNone(payload["refreshToken"])

    def test_user_registration_with_duplicate_username(self):
        settings.AUTO_LOGIN_AFTER_REGISTER = False
        with domain(self.domain.id):
            response = self.query(
                self.register_mutation,
                variables={
                    "username": "polawat",
                    "invitationCode": "1234",
                    "firstName": "john",
                    "lastName": "Doe",
                    "email": "pphetra@gmail.com",
                },
            )
            self.assertResponseHasErrors(response)
