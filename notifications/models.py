from typing import List
from dataclasses import dataclass
from django.db import models
from firebase_admin import messaging
from firebase_admin.messaging import ApsAlert

from accounts.models import BaseModel, User
from podd_api import settings


@dataclass
class Receiver:
    method: str
    to: str

    @staticmethod
    def parse(receivers: str) -> List["Receiver"]:
        results = []
        for receiver in receivers.split(","):
            [method, to] = receiver.strip().split(":")
            results.append(Receiver(method=method, to=to))
        return results


class Message(BaseModel):
    title = models.CharField(max_length=200)
    body = models.TextField()
    image = models.CharField(max_length=200, blank=True)

    def send_user(self, user: User):
        UserMessage.objects.create(message=self, user=user, is_seen=False).send()

    def send_email(self, email: str):
        print(f"send email: {email}, {self.body}")

    def send_sms(self, sms: str):
        print(f"send sms: {sms}, {self.body}")

    def send_by(self, receiver: Receiver):
        if receiver.method == "user":
            try:
                user = User.objects.get(username=receiver.to)
                self.send_user(user)
            except User.DoesNotExist:
                pass
        elif receiver.method == "email":
            self.send_email(receiver.to)
        elif receiver.method == "sms":
            self.send_sms(receiver.to)

    def send(self, receivers: str):
        for receiver in Receiver.parse(receivers):
            self.send_by(receiver)


class UserMessage(BaseModel):
    message = models.ForeignKey(Message, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    is_seen = models.BooleanField(default=False, blank=True)

    def send(self):
        fcm_token = self.user.fcm_token
        if fcm_token:
            alert = ApsAlert(title=self.message.title, body=self.message.body)
            aps = messaging.Aps(alert=alert, sound="default")
            payload = messaging.APNSPayload(aps)

            fcm_msg = messaging.Message(
                notification=messaging.Notification(
                    title=self.message.title,
                    body=self.message.body,
                    image=self.image.body if self.message.image else None,
                ),
                data={
                    "user_message_id": str(self.id),
                },
                token=self.user.fcm_token,
                apns=messaging.APNSConfig(payload=payload),
            )
            res = messaging.send(
                fcm_msg,
                dry_run=settings.FCM_DRY_RUN,
            )
            return res
