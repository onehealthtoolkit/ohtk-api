from django.test import TestCase

from accounts.models import AuthorityUser, Authority
from accounts.utils import domain


class AuthoirtyUserTestCase(TestCase):
    def setUp(self):
        self.a1 = Authority.objects.create(code="a1", name="a1")

    def test_create_user(self):
        u1 = AuthorityUser.objects.create(
            username="test1", first_name="John", last_name="Doe", authority=self.a1
        )
        self.assertEqual("test1", u1.username)
        self.assertEqual("John", u1.first_name)
        self.assertEqual("Doe", u1.last_name)
        self.assertEqual(self.a1.id, u1.authority.id)
