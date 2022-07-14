from notifications.models import UserMessage
from podd_api.celery import app


@app.task
def update_is_seen(user_message_id):
    msg = UserMessage.objects.get(pk=user_message_id)
    if not msg.is_seen:
        msg.is_seen = True
        msg.save(update_fields=("is_seen",))
