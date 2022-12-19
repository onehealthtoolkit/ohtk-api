from django.dispatch import receiver
from easy_thumbnails.signals import saved_file

from observations.models import ObservationImage

from . import tasks


@receiver(
    saved_file,
    sender=ObservationImage,
    dispatch_uid="observation_image_signal_to_generate_thumbnail",
)
def on_observation_image_update(sender, fieldfile, **kwargs):
    tasks.generate_observation_image.delay(fieldfile.instance.id)
