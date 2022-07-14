import uuid

from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.contrib.gis.db import models

from accounts.models import BaseModel, User, Authority
from common.eval import build_eval_obj
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


class Image(BaseModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file = models.ImageField(upload_to="reports")
    report_type = models.ForeignKey(
        ContentType,
        limit_choices_to={
            "model__in": [c.__name__ for c in BaseReport.__subclasses__()]
        },
        on_delete=models.CASCADE,
    )
    report_id = models.UUIDField()
    report = GenericForeignKey("report_type", "report_id")


class AbstractIncidentReport(BaseReport):
    class Meta:
        abstract = True

    report_type = models.ForeignKey(
        ReportType, on_delete=models.PROTECT, related_name="%(class)ss"
    )
    data = models.JSONField()
    renderer_data = models.TextField(blank=True, default="")
    test_flag = models.BooleanField(default=False, blank=True)
    images = GenericRelation(
        Image,
        content_type_field="report_type",
        object_id_field="report_id",
    )
    cover_image = models.ForeignKey(
        Image, blank=True, null=True, on_delete=models.SET_NULL
    )


class IncidentReport(AbstractIncidentReport):
    incident_date = models.DateField()
    origin_data = models.JSONField()
    origin_renderer_data = models.TextField(blank=True, default="")
    gps_location = models.PointField(null=True, blank=True)
    relevant_authority_resolved = models.BooleanField(default=False, null=False)
    relevant_authorities = models.ManyToManyField(Authority, related_name="incidents")
    case_id = models.UUIDField(blank=True, null=True)

    def save(self, *args, **kwargs):
        self.renderer_data = self.report_type.render_data(
            {
                "data": self.data,
                "id": self.id,
                "incident_date": self.incident_date,
            }
        )
        if not self.origin_data:
            self.origin_data = self.data
            self.origin_renderer_data = self.renderer_data
        super(IncidentReport, self).save(*args, **kwargs)

    def resolve_relevant_authorities_by_area(self):
        found_authorities = Authority.objects.filter(area__contains=self.gps_location)
        for authority in found_authorities:
            self.relevant_authorities.add(authority)
        if found_authorities:
            self.relevant_authority_resolved = True
            self.save(update_fields=("relevant_authority_resolved",))

    def evaluate_context(self):
        return build_eval_obj(
            {
                "data": self.data,
                "report_date": self.created_at,
                "incident_date": self.incident_date,
                "gps_location": self.gps_location,
                "report_id": self.id,
                "report_type": {
                    "id": self.report_type.id,
                    "name": self.report_type.name,
                    "category": self.report_type.category,
                },
            }
        )


class ZeroReport(BaseReport):
    pass


class FollowUpReport(AbstractIncidentReport):
    incident = models.ForeignKey(
        IncidentReport, on_delete=models.CASCADE, related_name="followups"
    )

    def save(self, *args, **kwargs):
        renderer_data = self.report_type.render_data(
            {
                "data": self.data,
                "id": self.id,
                "incident_date": self.incident_date,
            }
        )
        if self.renderer_data != renderer_data:
            self.renderer_data = renderer_data
        super(FollowUpReport, self).save(*args, **kwargs)
