from django.test import TestCase

from accounts.models import User
from notifications.models import Message, UserMessage
from podd_api import settings


class UserMessageTestCase(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create(
            username="test",
            fcm_token="cAEB3jpvQ-SHtTrFmuHuhW:APA91bFAniPLajWJT21tJdA3IvSv1-6BiuyVlgGbFJldmrhiAPpVrrApGef3wryXMB1_sMcOEyAcI5U39fw5AVe9KB6e16_lmIYUd_IYE63xLNHL_moNOHagbA8x2w0emnIWlXQ-HD-d",
        )
        settings.FCM_DRY_RUN = True

    def test_send_message(self):
        msg = Message.objects.create(title="hello", body="hello world")
        msg.send(self.user)
        um = UserMessage.objects.get(message=msg)
        self.assertEqual(um.user_id, self.user.id)
        self.assertFalse(um.is_seen)
