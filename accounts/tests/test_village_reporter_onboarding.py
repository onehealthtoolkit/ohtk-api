from graphql_jwt.testcases import JSONWebTokenTestCase

from accounts.models import (
    Authority,
    AuthorityUser,
    InvitationCode,
    User,
    Village,
    VillageReporterAssignment,
)
from accounts.village_capability import set_village_capability_enabled


class VillageReporterOnboardingTests(JSONWebTokenTestCase):
    def setUp(self):
        self.super_user = User.objects.create(username="platform", is_superuser=True)
        self.authority = Authority.objects.create(name="test authority", code="TA")
        self.other_authority = Authority.objects.create(
            name="other authority", code="OA"
        )
        self.village1 = Village.objects.create(
            code="V001", name="Village One", authority=self.authority
        )
        self.village2 = Village.objects.create(
            code="V002", name="Village Two", authority=self.authority
        )
        self.other_village = Village.objects.create(
            code="V999", name="Other Village", authority=self.other_authority
        )

    def execute_create_invitation(self, variables):
        mutation = """
        mutation adminInvitationCodeCreate(
            $code: String!,
            $authorityId: Int!,
            $fromDate: DateTime!,
            $throughDate: DateTime!,
            $villageIds: [Int],
            $role: String
        ) {
            adminInvitationCodeCreate(
                code: $code,
                authorityId: $authorityId,
                fromDate: $fromDate,
                throughDate: $throughDate,
                villageIds: $villageIds,
                role: $role
            ) {
                result {
                    __typename
                    ... on AdminInvitationCodeCreateSuccess {
                        id
                        code
                        villages {
                            id
                            code
                        }
                    }
                    ... on AdminInvitationCodeCreateProblem {
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

    def execute_update_invitation(self, variables):
        mutation = """
        mutation adminInvitationCodeUpdate(
            $id: ID!,
            $code: String!,
            $authorityId: Int,
            $villageIds: [Int]
        ) {
            adminInvitationCodeUpdate(
                id: $id,
                code: $code,
                authorityId: $authorityId,
                villageIds: $villageIds
            ) {
                result {
                    __typename
                    ... on AdminInvitationCodeUpdateSuccess {
                        invitationCode {
                            id
                            code
                            villages {
                                code
                            }
                        }
                    }
                    ... on AdminInvitationCodeUpdateProblem {
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

    def execute_register(self, variables):
        mutation = """
        mutation authorityUserRegister(
            $username: String!,
            $invitationCode: String!,
            $firstName: String!,
            $lastName: String!,
            $email: String!
        ) {
            authorityUserRegister(
                username: $username,
                invitationCode: $invitationCode,
                firstName: $firstName,
                lastName: $lastName,
                email: $email
            ) {
                me {
                    id
                    username
                    assignedVillages {
                        id
                        code
                    }
                }
            }
        }
        """
        return self.client.execute(mutation, variables)

    def create_village_invitation(self, code, village_ids):
        self.client.authenticate(self.super_user)
        result = self.execute_create_invitation(
            {
                "code": code,
                "authorityId": self.authority.id,
                "fromDate": "2026-05-05T00:00:00.000Z",
                "throughDate": "2026-05-06T00:00:00.000Z",
                "villageIds": village_ids,
            }
        )
        self.assertIsNone(result.errors, result.errors)
        self.assertEqual(
            result.data["adminInvitationCodeCreate"]["result"]["__typename"],
            "AdminInvitationCodeCreateSuccess",
        )

    def test_single_village_invitation_registers_reporter_assignment(self):
        set_village_capability_enabled(True)
        self.create_village_invitation("VIL001", [self.village1.id])

        result = self.execute_register(
            {
                "username": "reporter-one",
                "invitationCode": "VIL001",
                "firstName": "Reporter",
                "lastName": "One",
                "email": "reporter-one@example.com",
            }
        )

        self.assertIsNone(result.errors, result.errors)
        profile = result.data["authorityUserRegister"]["me"]
        self.assertEqual(profile["assignedVillages"][0]["code"], "V001")
        reporter = AuthorityUser.objects.get(username="reporter-one")
        self.assertEqual(
            list(
                VillageReporterAssignment.objects.filter(reporter=reporter)
                .values_list("village__code", flat=True)
                .order_by("village__code")
            ),
            ["V001"],
        )

    def test_multi_village_invitation_registers_multiple_assignments(self):
        set_village_capability_enabled(True)
        self.create_village_invitation("VIL002", [self.village1.id, self.village2.id])

        result = self.execute_register(
            {
                "username": "reporter-two",
                "invitationCode": "VIL002",
                "firstName": "Reporter",
                "lastName": "Two",
                "email": "reporter-two@example.com",
            }
        )

        self.assertIsNone(result.errors, result.errors)
        assigned_codes = sorted(
            village["code"]
            for village in result.data["authorityUserRegister"]["me"][
                "assignedVillages"
            ]
        )
        self.assertEqual(assigned_codes, ["V001", "V002"])

    def test_invitation_rejects_village_outside_invitation_authority(self):
        set_village_capability_enabled(True)
        self.client.authenticate(self.super_user)
        result = self.execute_create_invitation(
            {
                "code": "VIL003",
                "authorityId": self.authority.id,
                "fromDate": "2026-05-05T00:00:00.000Z",
                "throughDate": "2026-05-06T00:00:00.000Z",
                "villageIds": [self.other_village.id],
            }
        )

        self.assertIsNone(result.errors, result.errors)
        fields = result.data["adminInvitationCodeCreate"]["result"]["fields"]
        self.assertEqual(fields[0]["name"], "village_ids")
        self.assertFalse(InvitationCode.objects.filter(code="VIL003").exists())

    def test_invitation_rejects_villages_when_capability_disabled(self):
        self.client.authenticate(self.super_user)
        result = self.execute_create_invitation(
            {
                "code": "VIL004",
                "authorityId": self.authority.id,
                "fromDate": "2026-05-05T00:00:00.000Z",
                "throughDate": "2026-05-06T00:00:00.000Z",
                "villageIds": [self.village1.id],
            }
        )

        self.assertIsNone(result.errors, result.errors)
        fields = result.data["adminInvitationCodeCreate"]["result"]["fields"]
        self.assertEqual(fields[0]["name"], "village_ids")
        self.assertFalse(InvitationCode.objects.filter(code="VIL004").exists())

    def test_invitation_rejects_villages_for_non_reporter_role(self):
        set_village_capability_enabled(True)
        self.client.authenticate(self.super_user)
        result = self.execute_create_invitation(
            {
                "code": "VIL006",
                "authorityId": self.authority.id,
                "fromDate": "2026-05-05T00:00:00.000Z",
                "throughDate": "2026-05-06T00:00:00.000Z",
                "villageIds": [self.village1.id],
                "role": AuthorityUser.Role.ADMIN,
            }
        )

        self.assertIsNone(result.errors, result.errors)
        fields = result.data["adminInvitationCodeCreate"]["result"]["fields"]
        self.assertEqual(fields[0]["name"], "role")
        self.assertFalse(InvitationCode.objects.filter(code="VIL006").exists())

    def test_authority_only_invitation_still_registers_when_capability_disabled(self):
        invitation = InvitationCode.objects.create(
            code="AUTH01",
            authority=self.authority,
            role=AuthorityUser.Role.REPORTER,
        )

        result = self.execute_register(
            {
                "username": "reporter-three",
                "invitationCode": invitation.code,
                "firstName": "Reporter",
                "lastName": "Three",
                "email": "reporter-three@example.com",
            }
        )

        self.assertIsNone(result.errors, result.errors)
        reporter = AuthorityUser.objects.get(username="reporter-three")
        self.assertFalse(
            VillageReporterAssignment.objects.filter(reporter=reporter).exists()
        )

    def test_update_invitation_replaces_villages(self):
        set_village_capability_enabled(True)
        invitation = InvitationCode.objects.create(
            code="VIL005",
            authority=self.authority,
            role=AuthorityUser.Role.REPORTER,
        )
        invitation.villages.set([self.village1])
        self.client.authenticate(self.super_user)

        result = self.execute_update_invitation(
            {
                "id": invitation.id,
                "code": "VIL005",
                "villageIds": [self.village2.id],
            }
        )

        self.assertIsNone(result.errors, result.errors)
        villages = result.data["adminInvitationCodeUpdate"]["result"]["invitationCode"][
            "villages"
        ]
        self.assertEqual([village["code"] for village in villages], ["V002"])

    def test_admin_cannot_update_invitation_to_outside_authority(self):
        set_village_capability_enabled(True)
        invitation = InvitationCode.objects.create(
            code="VIL007",
            authority=self.authority,
            role=AuthorityUser.Role.REPORTER,
        )
        invitation.villages.set([self.village1])
        admin = AuthorityUser.objects.create(
            username="authority-admin",
            authority=self.authority,
            role=AuthorityUser.Role.ADMIN,
        )
        self.client.authenticate(admin)

        result = self.execute_update_invitation(
            {
                "id": invitation.id,
                "code": "VIL007",
                "authorityId": self.other_authority.id,
                "villageIds": [self.other_village.id],
            }
        )

        self.assertIsNotNone(result.errors)
        invitation.refresh_from_db()
        self.assertEqual(invitation.authority_id, self.authority.id)
        self.assertEqual(
            list(invitation.villages.values_list("code", flat=True)), ["V001"]
        )

    def test_query_me_returns_assigned_villages(self):
        set_village_capability_enabled(True)
        reporter = AuthorityUser.objects.create(
            username="reporter-four",
            authority=self.authority,
            role=AuthorityUser.Role.REPORTER,
        )
        VillageReporterAssignment.objects.create(
            reporter=reporter, village=self.village1
        )
        self.client.authenticate(reporter)
        query = """
        query me {
            me {
                assignedVillages {
                    code
                }
            }
        }
        """

        result = self.client.execute(query, {})

        self.assertIsNone(result.errors, result.errors)
        self.assertEqual(result.data["me"]["assignedVillages"][0]["code"], "V001")

    def test_authority_user_query_returns_assigned_villages(self):
        set_village_capability_enabled(True)
        reporter = AuthorityUser.objects.create(
            username="reporter-five",
            authority=self.authority,
            role=AuthorityUser.Role.REPORTER,
        )
        VillageReporterAssignment.objects.create(
            reporter=reporter, village=self.village1
        )
        self.client.authenticate(self.super_user)
        query = """
        query authorityUser($id: ID!) {
            authorityUser(id: $id) {
                assignedVillages {
                    code
                }
            }
        }
        """

        result = self.client.execute(query, {"id": reporter.id})

        self.assertIsNone(result.errors, result.errors)
        self.assertEqual(
            result.data["authorityUser"]["assignedVillages"][0]["code"], "V001"
        )

    def test_authority_user_query_returns_village_assignment_census_roles(self):
        set_village_capability_enabled(True)
        reporter = AuthorityUser.objects.create(
            username="reporter-six",
            authority=self.authority,
            role=AuthorityUser.Role.REPORTER,
        )
        VillageReporterAssignment.objects.create(
            reporter=reporter,
            village=self.village1,
            census_role=VillageReporterAssignment.CensusRole.VOLUNTEER,
        )
        self.client.authenticate(self.super_user)
        query = """
        query authorityUser($id: ID!) {
            authorityUser(id: $id) {
                assignedVillageAssignments {
                    censusRole
                    village {
                        code
                    }
                }
            }
        }
        """

        result = self.client.execute(query, {"id": reporter.id})

        self.assertIsNone(result.errors, result.errors)
        assignment = result.data["authorityUser"]["assignedVillageAssignments"][0]
        self.assertEqual(assignment["village"]["code"], "V001")
        self.assertEqual(assignment["censusRole"], "VOL")

    def test_admin_can_replace_reporter_village_assignments_with_census_roles(self):
        set_village_capability_enabled(True)
        reporter = AuthorityUser.objects.create(
            username="reporter-seven",
            authority=self.authority,
            role=AuthorityUser.Role.REPORTER,
        )
        VillageReporterAssignment.objects.create(
            reporter=reporter,
            village=self.village1,
            census_role=VillageReporterAssignment.CensusRole.OFFICIAL,
        )
        self.client.authenticate(self.super_user)
        mutation = """
        mutation adminAuthorityUserUpdate(
            $id: ID!,
            $authorityId: Int!,
            $username: String!,
            $firstName: String!,
            $lastName: String!,
            $email: String!,
            $role: String,
            $villageAssignments: [VillageReporterAssignmentInput]
        ) {
            adminAuthorityUserUpdate(
                id: $id,
                authorityId: $authorityId,
                username: $username,
                firstName: $firstName,
                lastName: $lastName,
                email: $email,
                role: $role,
                villageAssignments: $villageAssignments
            ) {
                result {
                    __typename
                    ... on AdminAuthorityUserUpdateSuccess {
                        authorityUser {
                            assignedVillageAssignments {
                                censusRole
                                village {
                                    code
                                }
                            }
                        }
                    }
                    ... on AdminAuthorityUserUpdateProblem {
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
                "id": reporter.id,
                "authorityId": self.authority.id,
                "username": "reporter-seven",
                "firstName": "Reporter",
                "lastName": "Seven",
                "email": "reporter-seven@example.com",
                "role": AuthorityUser.Role.REPORTER,
                "villageAssignments": [
                    {
                        "villageId": self.village2.id,
                        "censusRole": VillageReporterAssignment.CensusRole.VOLUNTEER,
                    }
                ],
            },
        )

        self.assertIsNone(result.errors, result.errors)
        payload = result.data["adminAuthorityUserUpdate"]["result"]
        self.assertEqual(payload["__typename"], "AdminAuthorityUserUpdateSuccess")
        assignment = payload["authorityUser"]["assignedVillageAssignments"][0]
        self.assertEqual(assignment["village"]["code"], "V002")
        self.assertEqual(assignment["censusRole"], "VOL")
        self.assertEqual(
            list(
                VillageReporterAssignment.objects.filter(reporter=reporter)
                .values_list("village__code", "census_role")
                .order_by("village__code")
            ),
            [("V002", VillageReporterAssignment.CensusRole.VOLUNTEER)],
        )

    def test_reporter_assignment_update_rejects_non_reporter_role(self):
        set_village_capability_enabled(True)
        reporter = AuthorityUser.objects.create(
            username="reporter-eight",
            authority=self.authority,
            role=AuthorityUser.Role.REPORTER,
        )
        self.client.authenticate(self.super_user)
        mutation = """
        mutation adminAuthorityUserUpdate(
            $id: ID!,
            $authorityId: Int!,
            $username: String!,
            $firstName: String!,
            $lastName: String!,
            $email: String!,
            $role: String,
            $villageAssignments: [VillageReporterAssignmentInput]
        ) {
            adminAuthorityUserUpdate(
                id: $id,
                authorityId: $authorityId,
                username: $username,
                firstName: $firstName,
                lastName: $lastName,
                email: $email,
                role: $role,
                villageAssignments: $villageAssignments
            ) {
                result {
                    __typename
                    ... on AdminAuthorityUserUpdateProblem {
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
                "id": reporter.id,
                "authorityId": self.authority.id,
                "username": "reporter-eight",
                "firstName": "Reporter",
                "lastName": "Eight",
                "email": "reporter-eight@example.com",
                "role": AuthorityUser.Role.OFFICER,
                "villageAssignments": [
                    {
                        "villageId": self.village1.id,
                        "censusRole": VillageReporterAssignment.CensusRole.OFFICIAL,
                    }
                ],
            },
        )

        self.assertIsNone(result.errors, result.errors)
        payload = result.data["adminAuthorityUserUpdate"]["result"]
        self.assertEqual(payload["__typename"], "AdminAuthorityUserUpdateProblem")
        self.assertEqual(payload["fields"][0]["name"], "village_assignments")
