from django.db import models

from accounts.models import BaseModel


class ReporterNotification(BaseModel):
    description = models.TextField(default="", blank=True)
    condition = models.TextField()
    template = models.TextField()
    is_active = models.BooleanField(default=True, blank=True)
