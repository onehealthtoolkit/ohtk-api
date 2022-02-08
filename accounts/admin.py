from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from accounts.models import AuthorityUser, User, Authority, Domain, InvitationCode


class BasModelAdmin(admin.ModelAdmin):
    exclude = ("deleted_at",)


@admin.register(Domain)
class DomainAdmin(BasModelAdmin):
    list_display = ("name",)


@admin.register(User)
class UserAdmin(UserAdmin):
    list_display = ("username", "first_name", "last_name")


@admin.register(AuthorityUser)
class AuthorityUserAdmin(BasModelAdmin):
    list_display = ("username", "first_name", "last_name", "authority")


@admin.register(Authority)
class AuthorityAdmin(BasModelAdmin):
    search_fields = (
        "name",
        "code",
    )
    list_display = ("code", "name")
    autocomplete_fields = ["inherits"]


@admin.register(InvitationCode)
class InvitationCodeAdmin(BasModelAdmin):
    list_display = (
        "code",
        "authority",
    )
