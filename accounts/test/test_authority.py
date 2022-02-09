from django.db import IntegrityError
from django.test import TestCase

from accounts.models import Authority
from accounts.utils import domain


class AuthorityTestCase(TestCase):
    def setUp(self):
        pass

    def test_create_authority(self):
        a1 = Authority.objects.create(code="bkk", name="Bangkok")
        self.assertEqual(a1.code, "bkk")
        self.assertEqual(a1.name, "Bangkok")

    def test_authority_code_must_be_unique(self):
        a1 = Authority.objects.create(code="bkk", name="Bangkok")
        try:
            a2 = Authority.objects.create(code="bkk", name="another")
            self.fail("code can not be duplicate")
        except IntegrityError:
            pass


class AuthorityInheritTestCase(TestCase):
    def setUp(self):
        self.bkk = Authority.objects.create(code="bkk", name="Bangkok")
        self.district1 = Authority.objects.create(code="district1", name="district1")
        self.district2 = Authority.objects.create(code="district2", name="district2")
        self.subdistrict1_1 = Authority.objects.create(
            code="subdistrict1_1", name="subdistrict1_1"
        )
        self.district1.inherits.add(self.bkk)
        self.district2.inherits.add(self.bkk)
        self.subdistrict1_1.inherits.add(self.district1)

    def test_all_inherits_up(self):
        chains = self.subdistrict1_1.all_inherits_up()
        self.assertTrue(self.bkk in chains)
        self.assertTrue(self.district1 in chains)
        self.assertTrue(self.subdistrict1_1 in chains)
        self.assertEqual(3, len(chains))

        chains = self.district2.all_inherits_up()
        self.assertTrue(self.bkk in chains)
        self.assertTrue(self.district2 in chains)
        self.assertEqual(2, len(chains))

    def test_all_inherits_down(self):
        chains = self.bkk.all_inherits_down()
        self.assertEqual(4, len(chains))
        self.assertTrue(self.bkk in chains)
        self.assertTrue(self.district1 in chains)
        self.assertTrue(self.district2 in chains)
        self.assertTrue(self.subdistrict1_1 in chains)

        chains = self.district1.all_inherits_down()
        self.assertEqual(2, len(chains))
        self.assertTrue(self.district1 in chains)
        self.assertTrue(self.subdistrict1_1 in chains)

        chains = self.district2.all_inherits_down()
        self.assertEqual(1, len(chains))
        self.assertTrue(self.district2 in chains)
