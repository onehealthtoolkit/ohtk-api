from django.db import IntegrityError
from django.test import TestCase

from accounts.models import Domain, Authority
from accounts.utils import domain


class AuthorityTestCase(TestCase):
    def setUp(self):
        self.domain1 = Domain.objects.create(code="th", name="thailand")
        self.domain2 = Domain.objects.create(code="sg", name="singapore")

    def test_create_authority(self):
        with domain(self.domain1.id):
            a1 = Authority.objects.create(code="bkk", name="Bangkok")
            self.assertEqual(a1.code, "bkk")
            self.assertEqual(a1.name, "Bangkok")
            self.assertEqual(a1.domain.id, self.domain1.id)

    def test_authority_code_must_be_unique(self):
        with domain(self.domain1.id):
            a1 = Authority.objects.create(code="bkk", name="Bangkok")
            try:
                a2 = Authority.objects.create(code="bkk", name="another")
                self.fail("code can not be duplicate")
            except IntegrityError:
                pass


class AuthorityInheritTestCase(TestCase):
    def setUp(self):
        self.domain1 = Domain.objects.create(code="1", name="domain 1")
        with domain(self.domain1.id):
            self.bkk = Authority.objects.create(code="bkk", name="Bangkok")
            self.district1 = Authority.objects.create(
                code="district1", name="district1"
            )
            self.district2 = Authority.objects.create(
                code="district2", name="district2"
            )
            self.subdistrict1_1 = Authority.objects.create(
                code="subdistrict1_1", name="subdistrict1_1"
            )
            self.district1.inherits.add(self.bkk)
            self.district2.inherits.add(self.bkk)
            self.subdistrict1_1.inherits.add(self.district1)

    def test_all_inherits_up(self):
        with domain(self.domain1.id):
            chains = self.subdistrict1_1.all_inherits_up()
            self.assertTrue(self.bkk in chains)
            self.assertTrue(self.district1 in chains)
            self.assertTrue(self.subdistrict1_1 in chains)
            self.assertEqual(3, len(chains))

        with domain(self.domain1.id):
            chains = self.district2.all_inherits_up()
            self.assertTrue(self.bkk in chains)
            self.assertTrue(self.district2 in chains)
            self.assertEqual(2, len(chains))

    def test_all_inherits_down(self):
        with domain(self.domain1.id):
            chains = self.bkk.all_inherits_down()
            self.assertEqual(4, len(chains))
            self.assertTrue(self.bkk in chains)
            self.assertTrue(self.district1 in chains)
            self.assertTrue(self.district2 in chains)
            self.assertTrue(self.subdistrict1_1 in chains)

        with domain(self.domain1.id):
            chains = self.district1.all_inherits_down()
            self.assertEqual(2, len(chains))
            self.assertTrue(self.district1 in chains)
            self.assertTrue(self.subdistrict1_1 in chains)

        with domain(self.domain1.id):
            chains = self.district2.all_inherits_down()
            self.assertEqual(1, len(chains))
            self.assertTrue(self.district2 in chains)
