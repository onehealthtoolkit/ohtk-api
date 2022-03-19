import uuid

from django.contrib.gis.db import models

from accounts.models import BaseModel, User
from . import ReportType

"""
                         ┌────────────┐         ┌────────────┐  
                         │ BaseReport │───────○┼│    User    │  
                         └────────────┘         └────────────┘  
                                △                               
         ┌──────────────────────┼─────────────────────┐         
         │                      │                     │         
         │                      │                     │         
┌─────────────────┐   ┌─────────────────┐    ┌─────────────────┐
│   Zero Report   │   │ Incident Report │┼┼──│ FollowUp Report │
└─────────────────┘   └─────────────────┘    └─────────────────┘
"""


class BaseReport(BaseModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    platform = models.CharField(max_length=20, blank=True, null=True)
    reported_by = models.ForeignKey(
        User,
        blank=True,
        null=True,
        related_name="%(class)s",
        on_delete=models.PROTECT,
    )

    class Meta:
        abstract = True


class IncidentReport(BaseReport):
    incident_date = models.DateField()
    report_type = models.ForeignKey(
        ReportType, on_delete=models.PROTECT, related_name="incidents"
    )
    data = models.JSONField()
    renderer_data = models.TextField(blank=True, default="")
    origin_data = models.JSONField()
    origin_renderer_data = models.TextField(blank=True, default="")
    gps_location = models.PointField(null=True, blank=True)
    test_flag = models.BooleanField(default=False, blank=True)

    def save(self, *args, **kwargs):
        self.renderer_data = self.report_type.render_data(self.data)
        if not self.origin_data:
            self.origin_data = self.data
            self.origin_renderer_data = self.renderer_data
        super(IncidentReport, self).save(*args, **kwargs)


class ZeroReport(BaseReport):
    pass


class FollowUpReport(BaseReport):
    incident = models.ForeignKey(
        IncidentReport, on_delete=models.CASCADE, related_name="followups"
    )
    data = models.JSONField()
    renderer_data = models.TextField(blank=True, default="")
    report_type = models.ForeignKey(
        ReportType, on_delete=models.PROTECT, related_name="followups"
    )

    def save(self, *args, **kwargs):
        renderer_data = self.report_type.render_data(self.data)
        if self.renderer_data != renderer_data:
            self.renderer_data = renderer_data
        super(FollowUpReport, self).save(*args, **kwargs)
