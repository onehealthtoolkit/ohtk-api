from django.test import TestCase
from django.utils.timezone import now, timedelta
from accounts.models import User
from dateutil.relativedelta import relativedelta


class UserModelTest(TestCase):
    def test_is_created_less_than(self):
        # Create a user
        user = User.objects.create(username="testuser")

        # Set the user's date_joined attribute to 6 hours ago
        user.date_joined = now() - timedelta(hours=6)
        user.save()

        self.assertFalse(user.was_joined_more_than(relativedelta(hours=7)))

        self.assertTrue(user.was_joined_more_than(relativedelta(hours=5)))
