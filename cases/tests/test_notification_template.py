from unittest.mock import patch

from cases.models import NotificationTemplate, AuthorityNotification
from cases.tests.base_testcase import BaseTestCase


class NotificationTemplateTestCase(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.notification_template = NotificationTemplate.objects.create(
            name="dengue report",
            type=NotificationTemplate.Type.REPORT,
            condition="True",
            report_type=self.dengue_report_type,
            title_template="to those who concern",
            body_template="patient: {{ data.name }}",
        )
        self.jatujak_notification = AuthorityNotification.objects.create(
            authority=self.jatujak,
            template=self.notification_template,
            to="email:pphetra@gmail.com",
        )

    def test_create_message_with_report(self):
        message = self.notification_template.create_message_with_report(
            self.dengue_report
        )
        self.assertEqual(message.title, self.notification_template.title_template)
        self.assertEqual(message.body, "patient: John Doe")

    def test_get_notifications_with_authorities(self):
        notifications = self.notification_template.get_notifications_with_authorities(
            self.dengue_report_jatujak.relevant_authorities.all()
        )
        self.assertIn(self.jatujak_notification, notifications)

    def test_send_report_notification(self):
        with patch.object(NotificationTemplate, "send_message") as mock_send_message:
            self.notification_template.send_report_notification(
                self.dengue_report_jatujak.id
            )
            mock_send_message.assert_called()
