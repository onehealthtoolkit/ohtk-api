from django.test import TestCase
from graphql_jwt.testcases import JSONWebTokenClient

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


class MyMessageTestCase(TestCase):
    client_class = JSONWebTokenClient

    def setUp(self) -> None:
        self.user = User.objects.create(
            username="test",
            fcm_token="cAEB3jpvQ-SHtTrFmuHuhW:APA91bFAniPLajWJT21tJdA3IvSv1-6BiuyVlgGbFJldmrhiAPpVrrApGef3wryXMB1_sMcOEyAcI5U39fw5AVe9KB6e16_lmIYUd_IYE63xLNHL_moNOHagbA8x2w0emnIWlXQ-HD-d",
        )
        self.msg1 = Message.objects.create(title="1", body="body1")
        self.user_msg1 = UserMessage.objects.create(user=self.user, message=self.msg1)

        self.msg2 = Message.objects.create(title="2", body="body2")
        self.user_msg2 = UserMessage.objects.create(user=self.user, message=self.msg2)

        self.client.authenticate(self.user)

    def test_my_messages_query(self):
        query = """
        query myMessages {
            myMessages {
                results {
                    id
                    message {
                        title
                        body
                    }
                    user {
                        id
                        username
                    }
                }                
            }
        }
        """
        result = self.client.execute(query, {})
        data = result.data["myMessages"]["results"]
        self.assertEqual(2, len(data))

    def test_my_messsage(self):
        query = """
                query myMessage($id: String!) {
                    myMessage(id: $id) {
                        id
                        message {
                            title
                            body
                        }
                        isSeen              
                    }
                }
                """
        result = self.client.execute(query, {"id": str(self.msg1.id)})
        data = result.data["myMessage"]
        self.assertFalse(data["isSeen"])

    def test_my_messsage_is_seen_change_to_true(self):
        query = """
                query myMessage($id: String!) {
                    myMessage(id: $id) {
                        id
                        message {
                            title
                            body
                        }
                        isSeen              
                    }
                }
                """
        result = self.client.execute(query, {"id": str(self.msg1.id)})
        data = result.data["myMessage"]
        self.assertFalse(data["isSeen"])

        # is_seen will change to True
        result = self.client.execute(query, {"id": str(self.msg1.id)})
        data = result.data["myMessage"]
        self.assertTrue(data["isSeen"])
