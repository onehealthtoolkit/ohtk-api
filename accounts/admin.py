from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django import forms

from accounts.forms import ConfigurationForm
from accounts.models import (
    AuthorityUser,
    User,
    Authority,
    InvitationCode,
    Configuration,
)


class BaseModelAdmin(admin.ModelAdmin):
    exclude = ("deleted_at",)


@admin.register(User)
class UserAdmin(UserAdmin):
    list_display = ("username", "first_name", "last_name")


@admin.register(AuthorityUser)
class AuthorityUserAdmin(BaseModelAdmin):
    list_display = ("username", "first_name", "last_name", "authority")


@admin.register(Authority)
class AuthorityAdmin(BaseModelAdmin):
    search_fields = (
        "name",
        "code",
    )
    list_display = ("code", "name")
    autocomplete_fields = ["inherits"]


@admin.register(InvitationCode)
class InvitationCodeAdmin(BaseModelAdmin):
    list_display = (
        "code",
        "authority",
    )


@admin.register(Configuration)
class ConfigurationAdmin(BaseModelAdmin):
    list_display = ("key",)
    form = ConfigurationForm
