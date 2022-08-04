from unittest.mock import patch
from django.test import TestCase
from accounts.models import User
from notifications.models import Message


class MessageTestCase(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create(username="test")
        self.message = Message.objects.create(title="test title", body="test body")

    def test_send_by_email(self):
        with patch.object(self.message, "send_email") as mock_send_email:
            self.message.send("email:pphetra@gmail.com")
            mock_send_email.assert_called_with("pphetra@gmail.com")

    def test_send_by_sms(self):
        with patch.object(self.message, "send_sms") as mock_send_sms:
            self.message.send("sms:66958107323")
            mock_send_sms.assert_called_with("66958107323")

    def test_send_by_user(self):
        with patch.object(self.message, "send_user") as mock_send_user:
            self.message.send("user:test")
            mock_send_user.assert_called_with(self.user)

    def test_send_multiple_mix(self):
        with patch.object(self.message, "send_user") as mock_send_user:
            with patch.object(self.message, "send_sms") as mock_send_sms:
                with patch.object(self.message, "send_email") as mock_send_email:
                    self.message.send(
                        "user:test, sms:66958107323, email:pphetra@gmail.com"
                    )
                    mock_send_email.assert_called_with("pphetra@gmail.com")
                    mock_send_sms.assert_called_with("66958107323")
                    mock_send_user.assert_called_with(self.user)
