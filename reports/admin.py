import json

from django.contrib import admin
from django.db.models import JSONField
from django.forms import widgets

from accounts.admin import BaseModelAdmin
from reports.models import Category, ReportType
from reports.models.report import IncidentReport


class PrettyJSONWidget(widgets.Textarea):
    def format_value(self, value):
        try:
            value = json.dumps(json.loads(value), indent=2, sort_keys=True)
            # these lines will try to adjust size of TextArea to fit to content
            row_lengths = [len(r) for r in value.split("\n")]
            self.attrs["rows"] = min(max(len(row_lengths) + 2, 10), 30)
            self.attrs["cols"] = min(max(max(row_lengths) + 2, 40), 120)
            return value
        except Exception as e:
            return super(PrettyJSONWidget, self).format_value(value)


@admin.register(Category)
class CategoryAdmin(BaseModelAdmin):
    list_display = ("name",)
    exclude = ("deleted_at",)


@admin.register(ReportType)
class ReportTypeAdmin(BaseModelAdmin):
    list_display = ("name",)
    formfield_overrides = {JSONField: {"widget": PrettyJSONWidget}}


@admin.register(IncidentReport)
class IncidentReport(BaseModelAdmin):
    list_display = (
        "incident_date",
        "report_type",
        "renderer_data",
        "test_flag",
        "updated_at",
    )
    list_filter = ("updated_at", "report_type", "test_flag")

    formfield_overrides = {JSONField: {"widget": PrettyJSONWidget}}
