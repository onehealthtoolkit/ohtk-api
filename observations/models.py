from django.contrib.gis.db import models
from django.template import Template, Context
from django.template.defaultfilters import striptags

from common.models import BaseModel, BaseModelManager


#
# ┌─────────────────────────┐             ┌─────────────────────────┐
# │                         │             │                         │
# │       Observation       │            ╱│       Observation       │
# │       Definition        │┼────────────│         Subject         │
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


class Subject(BaseModel):
    definition = models.ForeignKey(Definition, on_delete=models.CASCADE)
    gps_location = models.PointField(null=True, blank=True)
    title = models.CharField(max_length=255)
    description = models.TextField()
    identity = models.CharField(max_length=40)
    is_active = models.BooleanField(default=True)
    form_data = models.JSONField()

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


class SubjectMonitoringRecord(BaseModel):
    monitoring_definition = models.ForeignKey(
        MonitoringDefinition, on_delete=models.CASCADE
    )
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    title = models.TextField()
    description = models.TextField()
    is_active = models.BooleanField(default=True)
    form_data = models.JSONField()

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
