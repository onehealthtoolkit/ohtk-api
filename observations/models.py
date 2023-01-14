import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import List

from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.contrib.gis.db import models
from django.template import Template, Context
from django.template.defaultfilters import striptags
from easy_thumbnails.fields import ThumbnailerImageField

from accounts.models import User
from common.models import BaseModel, BaseModelManager


#
# ┌─────────────────────────┐             ┌─────────────────────────┐
# │                         │             │                         │
# │       Observation       │            ╱│       Observation       │
# │       Definition        │┼────────────│         Subject Record  │
# │                         │            ╲│                         │
# └─────────────────────────┘             └─────────────────────────┘
#              │                                       │
#              │                                       │
#              │                                       │
#              │                                       │
#             ╱│╲                                     ╱│╲
# ┌─────────────────────────┐             ┌─────────────────────────┐
# │                         │             │                         │
# │       Monitoring        │             │         Subject         │
# │       Definition        │┼────────────│    Monitoring Record    │
# │                         │             │                         │
# └─────────────────────────┘             └─────────────────────────┘


class Definition(BaseModel):
    @dataclass
    class DefinitionData:
        id: int
        updated_at: datetime

    objects = BaseModelManager()
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    register_form_definition = models.JSONField()
    title_template = models.TextField()
    description_template = models.TextField()
    identity_template = models.TextField()

    def render_title(self, data):
        template = self.title_template
        return Definition.render_template(template, data)

    def render_description(self, data):
        template = self.description_template
        return Definition.render_template(template, data)

    def render_identity(self, data):
        template = self.identity_template
        return Definition.render_template(template, data)

    @staticmethod
    def render_template(template, data):
        if template:
            t = Template(template)
            c = Context(data)
            return striptags(t.render(c))
        else:
            return ""

    @staticmethod
    def check_updated(data: List[DefinitionData]):
        existing_items = Definition.objects.all()
        updated_set = set([])
        removed_list = []
        for definition in existing_items:
            found = False
            for item in data:
                if str(definition.id) == str(item.id):
                    found = True
                    if definition.updated_at != item.updated_at:
                        updated_set.add(definition)
                    else:
                        for monitoring in definition.monitoringdefinition_set.all():
                            if monitoring.updated_at > item.updated_at:
                                updated_set.add(definition)
                                break
                    break
            if not found:
                updated_set.add(definition)
        for item in data:
            found = False
            for definition in existing_items:
                if str(definition.id) == str(item.id):
                    found = True
                    break
            if not found:
                removed_list.append({"id": item.id})

        return {
            "updated_list": list(updated_set),
            "removed_list": removed_list,
        }


class AbstractRecord(BaseModel):
    objects = BaseModelManager()

    class Meta:
        abstract = True

    images = GenericRelation(
        "observations.RecordImage",
        content_type_field="record_type",
        object_id_field="record_id",
    )
    cover_image = models.ForeignKey(
        "observations.RecordImage",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )
    is_active = models.BooleanField(default=True)
    form_data = models.JSONField()

    reported_by = models.ForeignKey(
        User,
        blank=True,
        null=True,
        related_name="%(class)s",
        on_delete=models.PROTECT,
    )


class RecordImage(BaseModel):
    objects = BaseModelManager()

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file = ThumbnailerImageField(upload_to="observations")
    record_type = models.ForeignKey(
        ContentType,
        limit_choices_to={
            "model__in": [c.__name__ for c in AbstractRecord.__subclasses__()]
        },
        on_delete=models.CASCADE,
    )
    record_id = models.UUIDField()
    record = GenericForeignKey("record_type", "record_id")

    def generate_thumbnails(self):
        if hasattr(self.file, "generate_all_thumbnails"):
            self.file.generate_all_thumbnails()


class SubjectRecord(AbstractRecord):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    definition = models.ForeignKey(Definition, on_delete=models.CASCADE)
    gps_location = models.PointField(null=True, blank=True)
    title = models.CharField(max_length=255)
    description = models.TextField()
    identity = models.CharField(max_length=40)

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
            "data": self.form_data,
            "report_id": self.id,
            "definition_name": self.definition.name,
            "report_date": self.created_at,
            "report_date_str": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "report_date_no_time_str": self.created_at.strftime("%Y-%m-%d"),
            "gps_location": self.gps_location_str,
        }

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.title = self.definition.render_title(self.render_data_context())
        self.description = self.definition.render_description(
            self.render_data_context()
        )
        self.identity = self.definition.render_identity(self.render_data_context())
        super().save(update_fields=["title", "description", "identity"])


class MonitoringDefinition(BaseModel):
    objects = BaseModelManager()
    definition = models.ForeignKey(Definition, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    form_definition = models.JSONField()
    title_template = models.TextField()
    description_template = models.TextField()

    def render_title(self, data):
        template = self.title_template
        return Definition.render_template(template, data)

    def render_description(self, data):
        template = self.description_template
        return Definition.render_template(template, data)

    @staticmethod
    def render_template(template, data):
        if template:
            t = Template(template)
            c = Context(data)
            return striptags(t.render(c))
        else:
            return ""


class MonitoringRecord(AbstractRecord):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    monitoring_definition = models.ForeignKey(
        MonitoringDefinition, on_delete=models.CASCADE
    )
    subject = models.ForeignKey(SubjectRecord, on_delete=models.CASCADE)
    title = models.TextField()
    description = models.TextField()

    def render_data_context(self):
        return {
            "data": self.form_data,
        }

    def save(self, *args, **kwargs):
        self.title = self.monitoring_definition.render_title(self.render_data_context())
        self.description = self.monitoring_definition.render_description(
            self.render_data_context()
        )
        super().save(*args, **kwargs)
