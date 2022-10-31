import json

import channels
import django.dispatch
from asgiref.sync import async_to_sync
from django.db.models.signals import m2m_changed
from django.dispatch import receiver
from easy_thumbnails.signals import saved_file

from accounts.models import Authority
from reports.consumers import new_report_group_name
from reports.models import IncidentReport, Image
from django.db import connection
from . import tasks

incident_report_submitted = django.dispatch.Signal()
incident_report_resolved = django.dispatch.Signal()


@receiver(
    m2m_changed,
    sender=IncidentReport.relevant_authorities.through,
    dispatch_uid="report_signal_to_ws",
)
def on_create_report(sender, instance, action, reverse, model, pk_set, **kwargs):
    if action == "post_add":
        schema_name = connection.schema_name
        for authority_id in pk_set:
            for authority in Authority.objects.get(pk=authority_id).all_inherits_up():
                group_name = new_report_group_name(schema_name, authority.id)
                channel_layer = channels.layers.get_channel_layer()
                async_to_sync(channel_layer.group_send)(
                    group_name,
                    {
                        "type": "new.report",
                        "text": json.dumps(instance.template_context(), default=str),
                    },
                )


@receiver(
    saved_file,
    sender=Image,
    dispatch_uid="report_image_signal_to_generate_thumbnail",
)
def on_report_image_update(sender, fieldfile, **kwargs):
    tasks.generate_report_image.delay(fieldfile.instance.id)


@receiver(
    incident_report_submitted,
    sender=IncidentReport,
    dispatch_uid="report_signal_to_evaluate_reporter_notification",
)
def send_notification_to_reporter(sender, report, **kwargs):
    tasks.evaluate_reporter_notification.delay(report.id)
