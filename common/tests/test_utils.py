from django.test import SimpleTestCase

from common.utils import is_not_empty


class TestUtils(SimpleTestCase):
    def test_is_not_empty(self):
        self.assertIsNone(is_not_empty("name", "name value", "Name is not empty"))

    def test_is_empty(self):
        self.assertIsNotNone(is_not_empty("name", "", "Name is not empty"))
