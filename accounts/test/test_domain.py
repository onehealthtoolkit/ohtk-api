from django.db import IntegrityError
from django.test import TestCase

from accounts.models import Domain


class DomainTestCase(TestCase):
    def test_create_new_domain(self):
        cm = Domain.objects.create(code="cm", name="chiangmai")
        self.assertEqual(cm.name, "chiangmai")
        self.assertEqual(cm.code, "cm")

    def test_code_must_be_unique(self):
        cm = Domain.objects.create(code="cm", name="chiangmai")
        try:
            cm2 = Domain.objects.create(code="cm", name="chiangmai2")
            self.fail("duplicate code")
        except IntegrityError:
            pass

    def test_name_must_be_unique(self):
        cm = Domain.objects.create(code="cm", name="chiangmai")
        try:
            cm3 = Domain.objects.create(code="cm2", name="chiangmai")
            self.fail("duplicate name")
        except IntegrityError:
            pass
