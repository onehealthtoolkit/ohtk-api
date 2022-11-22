from django.db import models
from django.template import Template, Context
from django.template.defaultfilters import striptags

from accounts.models import User
from common.models import BaseModel, BaseModelManager
from notifications.models import Message, UserMessage
from reports.models import ReportType


class ReporterNotification(BaseModel):
    objects = BaseModelManager()

    description = models.TextField(default="", blank=True)
    condition = models.TextField()
    title_template = models.TextField(blank=True)
    template = models.TextField()
    is_active = models.BooleanField(default=True, blank=True)
    report_type = models.ForeignKey(
        ReportType, blank=True, null=True, on_delete=models.CASCADE
    )

    def send_message(self, context: dict, user: User):
        template_context = Context(context)
        title = ""
        message = ""
        if self.title_template:
            title_template = Template(self.title_template)
            title = striptags(title_template.render(template_context))

        if self.template:
            t = Template(self.template)
            message = striptags(t.render(template_context))

        reporter_message = Message.objects.create(title=title, body=message)
        reporter_message.send_user(user)
