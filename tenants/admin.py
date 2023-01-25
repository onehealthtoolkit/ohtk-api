# Register your models here.
from django.contrib import admin
from django_tenants.admin import TenantAdminMixin

from tenants.models import Client, Domain, ExternalDomain


@admin.register(Client)
class ClientAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ("name",)


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ("domain", "tenant")
    list_filter = ("tenant",)


@admin.register(ExternalDomain)
class ExternalDomainAdmin(admin.ModelAdmin):
    list_display = ("name", "domain")
    list_filter = ("name",)
    fields = (
        "name",
        "domain",
    )
