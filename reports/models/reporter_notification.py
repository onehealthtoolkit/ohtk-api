from django.db import models

from accounts.models import BaseModel
from reports.models import ReportType


class ReporterNotification(BaseModel):
    description = models.TextField(default="", blank=True)
    condition = models.TextField()
    template = models.TextField()
    is_active = models.BooleanField(default=True, blank=True)
    report_type = models.ForeignKey(
        ReportType, blank=True, null=True, on_delete=models.CASCADE
    )
