from unittest import TestCase

from accounts.utils import get_current_domain_id, domain


class DomainContextTestCase(TestCase):
    def test_get_current_domain_without_context(self):
        self.assertIsNone(get_current_domain_id())

    def test_get_current_domain_within_context(self):
        with domain(1):
            self.assertEqual(1, get_current_domain_id())
            with domain(2):
                self.assertEqual(2, get_current_domain_id())
