from django.db import models
from django.template import Template, Context
from django.template.defaultfilters import striptags

from accounts.models import BaseModel, User
from notifications.models import Message, UserMessage
from reports.models import ReportType


class ReporterNotification(BaseModel):
    description = models.TextField(default="", blank=True)
    condition = models.TextField()
    template = models.TextField()
    is_active = models.BooleanField(default=True, blank=True)
    report_type = models.ForeignKey(
        ReportType, blank=True, null=True, on_delete=models.CASCADE
    )

    def send_message(self, context: dict, user: User):
        if self.template:
            t = Template(self.template)
            c = Context(context)
            message = striptags(t.render(c))
        else:
            message = ""

        reporter_message = Message.objects.create(title="", body=message)
        reporter_message.send(user)
