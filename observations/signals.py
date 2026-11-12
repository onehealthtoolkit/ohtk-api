from django.dispatch import receiver
from easy_thumbnails.signals import saved_file

from common.commit_tasks import enqueue_after_commit
from observations.models import RecordImage

from . import tasks


@receiver(
    saved_file,
    sender=RecordImage,
    dispatch_uid="record_image_signal_to_generate_thumbnail",
)
def on_record_image_update(sender, fieldfile, **kwargs):
    enqueue_after_commit(tasks.generate_record_image, fieldfile.instance.id)
