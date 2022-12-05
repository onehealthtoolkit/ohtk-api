from django.db import models

from common.models import BaseModel


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
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    register_form_definition = models.JSONField()
    title_template = models.TextField()
    description_template = models.TextField()
    identity_template = models.TextField()


class Subject(BaseModel):
    definition = models.ForeignKey(Definition, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    description = models.TextField()
    identity = models.CharField(max_length=40)
    is_active = models.BooleanField(default=True)
    form_data = models.JSONField()


class MonitoringDefinition(BaseModel):
    definition = models.ForeignKey(Definition, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    form_definition = models.JSONField()
    title_template = models.TextField()
    description_template = models.TextField()


class SubjectMonitoringRecord(BaseModel):
    monitoring_definition = models.ForeignKey(
        MonitoringDefinition, on_delete=models.CASCADE
    )
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    title = models.TextField()
    description = models.TextField()
    is_active = models.BooleanField(default=True)
    form_data = models.JSONField()
