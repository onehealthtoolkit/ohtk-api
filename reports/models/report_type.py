import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import List

from django.contrib.gis.db import models
from django.db.models import Q
from django.template import Template, Context
from django.template.defaultfilters import striptags

from accounts.models import Authority
from common.models import BaseModel, BaseModelManager
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
    followup_definition = models.JSONField(null=True, blank=True)
    authorities = models.ManyToManyField(
        Authority,
        related_name="reportTypes",
    )
    renderer_data_template = models.TextField(blank=True, null=True)
    renderer_followup_data_template = models.TextField(blank=True, null=True)
    ordering = models.IntegerField(default=0)
    state_definition = models.ForeignKey(
        "cases.StateDefinition",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )
    published = models.BooleanField(default=False)

    @staticmethod
    def filter_by_authority(authority: Authority, published_only=False):
        query = ReportType.objects.all()
        if published_only:
            query = query.filter(published=True)

        return query.filter(
            Q(authorities__in=authority.all_inherits_up()) | Q(authorities__isnull=True)
        )

    @staticmethod
    def check_updated_report_types_by_authority(
        authority: Authority,
        own_report_types: List[ReportTypeData],
    ):
        existing_items = ReportType.filter_by_authority(authority, published_only=True)
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
                removed_list.append({"id": item.id})

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

    def render_followup_data(self, form_data):
        template = self.renderer_followup_data_template
        if template:
            t = Template(template)
            c = Context(form_data)
            return striptags(t.render(c))
        else:
            return ""

    def publish(self):
        self.published = True
        self.save(update_fields=["published"])

    def unpublish(self):
        self.published = False
        self.save(update_fields=["published"])
