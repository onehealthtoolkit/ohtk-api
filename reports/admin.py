from django.contrib import admin

from accounts.admin import BasModelAdmin
from reports.models import Category, ReportType


@admin.register(Category)
class CategoryAdmin(BasModelAdmin):
    list_display = ("name",)
    exclude = ("deleted_at",)


@admin.register(ReportType)
class ReportTypeAdmin(BasModelAdmin):
    list_display = ("name",)
