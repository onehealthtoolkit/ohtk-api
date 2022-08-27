import json

import channels
from asgiref.sync import async_to_sync
from django.db.models.signals import m2m_changed
from django.dispatch import receiver

from accounts.models import Authority
from reports.consumers import new_report_group_name
from reports.models import IncidentReport


@receiver(
    m2m_changed,
    sender=IncidentReport.relevant_authorities.through,
    dispatch_id="report_signal_to_ws",
)
def on_create_report(sender, instance, action, reverse, model, pk_set, **kwargs):
    if action == "post_add":
        report_id = instance.id
        for authority_id in pk_set:
            for authority in Authority.objects.get(pk=authority_id).all_inherits_up():
                group_name = new_report_group_name(authority.id)
                channel_layer = channels.layers.get_channel_layer()
                async_to_sync(channel_layer.group_send)(
                    group_name,
                    {
                        "type": "new.report",
                        "text": json.dumps(
                            {
                                "report_id": report_id,
                            }
                        ),
                    },
                )
