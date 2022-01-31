from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from accounts.models import AuthorityUser, User, Authority


@admin.register(User)
class UserAdmin(UserAdmin):
    list_display = ("username", "first_name", "last_name")


@admin.register(AuthorityUser)
class AuthorityUserAdmin(admin.ModelAdmin):
    list_display = ("username", "first_name", "last_name", "authority")


@admin.register(Authority)
class AuthorityAdmin(admin.ModelAdmin):
    search_fields = (
        "name",
        "code",
    )
    list_display = ("code", "name")
    autocomplete_fields = ["inherits"]
