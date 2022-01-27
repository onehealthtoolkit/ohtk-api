from django.test import TestCase

from accounts.models import Domain, AuthorityUser, Authority
from accounts.utils import domain


class AuthoirtyUserTestCase(TestCase):
    def setUp(self):
        self.domain1 = Domain.objects.create(code="1", name="domain 1")
        with domain(self.domain1.id):
            self.a1 = Authority.objects.create(code="a1", name="a1")

    def test_create_user(self):
        with domain(self.domain1.id):
            u1 = AuthorityUser.objects.create(
                username="test1", first_name="John", last_name="Doe", authority=self.a1
            )
            self.assertEqual("test1", u1.username)
            self.assertEqual("John", u1.first_name)
            self.assertEqual("Doe", u1.last_name)
            self.assertEqual(self.a1.id, u1.authority.id)
