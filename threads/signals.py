import json

import channels.layers
from asgiref.sync import async_to_sync
from django.db.models.signals import post_save
from django.dispatch import receiver

from threads.consumers import new_comment_group_name
from threads.models import Comment, CommentAttachment
from django.db import connection
from easy_thumbnails.signals import saved_file
from . import tasks


@receiver(post_save, sender=Comment, dispatch_uid="comment_signal_to_ws")
def on_comment_update(sender, instance, **kwargs):
    schema_name = connection.schema_name
    thread_id = instance.thread_id
    group_name = new_comment_group_name(schema_name, thread_id)
    channel_layer = channels.layers.get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        group_name,
        {
            "type": "update.comment",
            "text": json.dumps(
                {
                    "thread_id": thread_id,
                }
            ),
        },
    )


@receiver(
    saved_file,
    sender=CommentAttachment,
    dispatch_uid="comment_attachment_signal_to_generate_thumbnail",
)
def on_comment_attachment_update(sender, fieldfile, **kwargs):
    tasks.generate_comment_attachment.delay(fieldfile.instance.id)
