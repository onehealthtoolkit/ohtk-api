from django.db import models
from firebase_admin import messaging
from firebase_admin.messaging import ApsAlert

from accounts.models import BaseModel, User
from podd_api import settings


class Message(BaseModel):
    title = models.CharField(max_length=200)
    body = models.TextField()
    image = models.CharField(max_length=200, blank=True)

    def send(self, user: User):
        UserMessage.objects.create(message=self, user=user, is_seen=False).send()


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
