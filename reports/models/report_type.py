import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import List

from django.contrib.gis.db import models
from django.template import Template, Context
from django.template.defaultfilters import striptags

from accounts.models import BaseModel, Authority, BaseModelManager
from . import Category


class ReportType(BaseModel):
    @dataclass
    class ReportTypeData:
        id: uuid.UUID
        updated_at: datetime

    objects = BaseModelManager()

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    definition = models.JSONField()
    authorities = models.ManyToManyField(
        Authority,
        related_name="reportTypes",
    )
    renderer_data_template = models.TextField(blank=True, null=True)
    ordering = models.IntegerField(default=0)
    state_definition = models.ForeignKey(
        "cases.StateDefinition",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )

    @staticmethod
    def filter_by_authority(authority: Authority):
        return ReportType.objects.filter(authorities__in=authority.all_inherits_up())

    @staticmethod
    def check_updated_report_types_by_authority(
        authority: Authority,
        own_report_types: List[ReportTypeData],
    ):
        existing_items = ReportType.filter_by_authority(authority)
        updated_list = []
        removed_list = []
        for report_type in existing_items:
            found = False
            for item in own_report_types:
                if report_type.id == item.id:
                    found = True
                    if report_type.updated_at != item.updated_at:
                        updated_list.append(report_type)
            if not found:
                updated_list.append(report_type)
        for item in own_report_types:
            found = False
            for report_type in existing_items:
                if report_type.id == item.id:
                    found = True
            if not found:
                removed_list.append(report_type)

        return {
            "updated_list": updated_list,
            "removed_list": removed_list,
        }

    def __str__(self) -> str:
        return self.name

    def to_data(self):
        return ReportType.ReportTypeData(id=self.id, updated_at=self.updated_at)

    def render_data(self, form_data):
        template = self.renderer_data_template
        if template:
            t = Template(template)
            c = Context(form_data)
            return striptags(t.render(c))
        else:
            return ""
