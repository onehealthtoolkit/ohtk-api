import uuid

from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.contrib.gis.db import models
from easy_thumbnails.fields import ThumbnailerImageField

from accounts.models import BaseModel, User, Authority, BaseModelManager
from common.eval import build_eval_obj
from threads.models import Thread
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
    objects = BaseModelManager()

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
    objects = BaseModelManager()

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file = ThumbnailerImageField(upload_to="reports")
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
    thread = models.ForeignKey(
        Thread,
        on_delete=models.SET_NULL,
        related_name="reports",
        blank=True,
        null=True,
    )

    @property
    def gps_location_str(self):
        if self.gps_location:
            x = self.gps_location.x
            y = self.gps_location.y
            return f"{x:.5f},{y:.5f}"
        else:
            return ""

    def render_data_context(self):
        return {
            "data": self.data,
            "id": self.id,
            "incident_date": self.incident_date,
        }

    def save(self, *args, **kwargs):
        self.renderer_data = self.report_type.render_data(self.render_data_context())
        if not self.origin_data:
            self.origin_data = self.data
            self.origin_renderer_data = self.renderer_data
        super().save(*args, **kwargs)

    def resolve_relevant_authorities_by_area(self):
        if self.gps_location:
            found_authorities = Authority.objects.filter(
                area__contains=self.gps_location
            )
            if found_authorities:
                self.relevant_authorities.add(*found_authorities)
                self.relevant_authority_resolved = True
                self.save(update_fields=("relevant_authority_resolved",))

    def evaluate_context(self):
        return build_eval_obj(self.template_context())

    def template_context(self):
        return {
            "data": self.data,
            "report_date": self.created_at,
            "incident_date": self.incident_date,
            "gps_location": self.gps_location_str,
            "renderer_data": self.renderer_data,
            "report_id": self.id,
            "report_type": {
                "id": self.report_type.id,
                "name": self.report_type.name,
                "category": self.report_type.category,
            },
        }


class ZeroReport(BaseReport):
    pass


class FollowUpReport(AbstractIncidentReport):
    incident = models.ForeignKey(
        IncidentReport, on_delete=models.CASCADE, related_name="followups"
    )

    def render_data_context(self):
        return {
            "data": self.data,
            "id": self.id,
            "incident_data": self.incident.data,
        }

    def save(self, *args, **kwargs):
        self.renderer_data = self.report_type.render_followup_data(
            self.render_data_context()
        )
        super().save(*args, **kwargs)
