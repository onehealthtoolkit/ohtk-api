from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from graphql_jwt.testcases import JSONWebTokenTestCase

from accounts.models import Authority, AuthorityUser


class AdminUserFilterTests(JSONWebTokenTestCase):
    query = """
        query Users($ids: [ID], $role: String, $q: String,
                    $from: DateTime, $through: DateTime, $offset: Int = 0) {
            adminAuthorityUserQuery(authorityIds: $ids, role: $role, q: $q,
                dateJoinedGte: $from, dateJoinedLte: $through,
                limit: 1, offset: $offset, ordering: "username,asc") {
                totalCount
                results { username }
            }
        }
    """

    def setUp(self):
        self.a = Authority.objects.create(code="A", name="Selected authority")
        self.b = Authority.objects.create(code="B", name="Other authority")
        self.a.inherits.add(self.b)
        self.reporter = AuthorityUser.objects.create(
            username="alice", authority=self.a, role=AuthorityUser.Role.REPORTER
        )
        self.officer = AuthorityUser.objects.create(
            username="bob", authority=self.a, role=AuthorityUser.Role.OFFICER
        )
        self.other = AuthorityUser.objects.create(
            username="carol", authority=self.b, role=AuthorityUser.Role.REPORTER
        )
        self.client.authenticate(get_user_model().objects.create(
            username="superuser", is_superuser=True
        ))

    def fetch(self, variables, names, total):
        result = self.client.execute(self.query, variables)
        self.assertIsNone(result.errors)
        data = result.data["adminAuthorityUserQuery"]
        self.assertEqual(data["totalCount"], total)
        self.assertEqual([u["username"] for u in data["results"]], names)

    def test_selected_authority_excludes_other_authority(self):
        self.fetch({"ids": [str(self.a.pk)]}, ["alice"], 2)

    def test_multiple_authorities(self):
        self.fetch({"ids": [str(self.a.pk), str(self.b.pk)]}, ["alice"], 3)

    def test_empty_selection_does_not_filter(self):
        self.fetch({"ids": []}, ["alice"], 3)

    def test_role_and_text_are_combined_with_authority(self):
        self.fetch({"ids": [str(self.a.pk)], "role": "OFC", "q": "bob"}, ["bob"], 1)
        self.fetch({"ids": [str(self.a.pk)], "role": "REP", "q": "carol"}, [], 0)

    def test_dates_are_combined_with_authority(self):
        now = timezone.now()
        AuthorityUser.objects.filter(pk=self.reporter.pk).update(
            date_joined=now - timedelta(days=5)
        )
        self.fetch({"ids": [str(self.a.pk)],
                    "from": (now - timedelta(days=1)).isoformat(),
                    "through": (now + timedelta(days=1)).isoformat()}, ["bob"], 1)

    def test_pagination_retains_filter_and_count(self):
        self.fetch({"ids": [str(self.a.pk)], "offset": 1}, ["bob"], 2)

    def test_new_filter_does_not_expand_officer_scope(self):
        self.client.authenticate(self.officer)
        self.fetch({"ids": [str(self.b.pk)]}, [], 0)

    def test_new_filter_does_not_expand_admin_scope(self):
        self.officer.role = AuthorityUser.Role.ADMIN
        self.officer.save(update_fields=["role"])
        self.client.authenticate(self.officer)
        self.fetch({"ids": [str(self.b.pk)]}, [], 0)

    def test_legacy_decimal_argument_still_works(self):
        result = self.client.execute("""
            query Legacy($authorities: Decimal) {
                adminAuthorityUserQuery(authorities: $authorities) {
                    results { username }
                }
            }
        """, {"authorities": str(self.a.pk)})
        self.assertIsNone(result.errors)
        self.assertCountEqual([u["username"] for u in result.data[
            "adminAuthorityUserQuery"]["results"]], ["alice", "bob"])
