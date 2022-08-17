import graphene
import django_filters
from django.db.models import Q
from easy_thumbnails.files import get_thumbnailer
from graphene_django import DjangoObjectType

from django.contrib.gis.db import models
from graphene_django.converter import convert_django_field

from accounts.models import Authority, AuthorityUser, InvitationCode, Feature, User
from common.converter import GeoJSON
from common.types import AdminValidationProblem


@convert_django_field.register(models.PointField)
@convert_django_field.register(models.PolygonField)
@convert_django_field.register(models.MultiPolygonField)
def convert_geofield_to_string(field, registry=None):
    return GeoJSON(description=field.help_text, required=not field.null)


class AuthorityInheritType(DjangoObjectType):
    class Meta:
        model = Authority
        fields = (
            "id",
            "code",
            "name",
        )


class AuthorityType(DjangoObjectType):
    class Meta:
        model = Authority
        fields = (
            "id",
            "code",
            "name",
            "area",
        )
        filter_fields = {"name": ["istartswith", "exact"]}

    inherits = graphene.List(AuthorityInheritType, required=True)

    def resolve_inherits(self, info, **kwargs):
        results = []
        for authority in self.inherits.all():
            results.append(authority)
        return results


class AdminAuthorityQueryType(DjangoObjectType):
    class Meta:
        model = Authority
        fields = (
            "id",
            "code",
            "name",
        )
        filter_fields = {"name": ["istartswith", "exact"]}


class AdminAuthorityUserQueryFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(method="q_filter")

    class Meta:
        model = AuthorityUser
        fields = []

    def q_filter(self, queryset, name, value):
        return queryset.filter(
            Q(first_name__icontains=value)
            | Q(last_name__icontains=value)
            | Q(username__icontains=value)
            | Q(email__icontains=value)
        )


class AdminAuthorityUserQueryType(DjangoObjectType):
    class Meta:
        model = AuthorityUser
        fields = ("id", "username", "first_name", "last_name", "email", "role")
        filterset_class = AdminAuthorityUserQueryFilter


class AdminInvitationCodeQueryType(DjangoObjectType):
    class Meta:
        model = InvitationCode
        fields = ("id", "code", "authority", "from_date", "through_date", "role")
        filter_fields = {
            "code": ["istartswith", "exact"],
        }


class InvitationCodeType(DjangoObjectType):
    class Meta:
        model = InvitationCode
        fields = ("id", "authority", "code", "from_date", "through_date", "role")


class UserType(DjangoObjectType):
    telephone = graphene.String()
    avatar_url = graphene.String(required=False)

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "first_name",
            "last_name",
            "telephone",
        )

    def resolve_telephone(self, info):
        if self.is_authority_user:
            return self.authorityuser.telephone
        else:
            return ""

    def resolve_avatar_url(self, info):
        if self.avatar:
            return get_thumbnailer(self.avatar)["thumbnail"]
        else:
            return None


class AuthorityUserType(DjangoObjectType):
    class Meta:
        model = AuthorityUser
        fields = (
            "id",
            "authority",
            "username",
            "first_name",
            "last_name",
            "email",
            "telephone",
            "role",
        )


class UserProfileType(graphene.ObjectType):
    id = graphene.Int(required=True)
    username = graphene.String(required=True)
    first_name = graphene.String(required=True)
    last_name = graphene.String(required=True)
    email = graphene.String()
    authority_name = graphene.String(required=False)
    authority_id = graphene.Int(required=False)
    avatar_url = graphene.String(required=False)
    is_staff = graphene.Boolean()
    is_superuser = graphene.Boolean()
    role = graphene.String()

    def resolve_authority_name(self, info):
        if self.is_authority_user:
            return self.authority.name
        return ""

    def resolve_authority_id(self, info):
        if self.is_authority_user:
            return self.authority.id
        return 0

    def resolve_role(self, info):
        if self.is_authority_user:
            return self.role
        else:
            return ""

    def resolve_avatar_url(self, info):
        if self.avatar:
            return get_thumbnailer(self.avatar)["thumbnail"]
        else:
            return None


class CheckInvitationCodeType(DjangoObjectType):
    class Meta:
        model = InvitationCode
        fields = ("code", "authority")


class FeatureType(DjangoObjectType):
    class Meta:
        model = Feature


class AdminAuthorityCreateSuccess(DjangoObjectType):
    class Meta:
        model = Authority


class AdminAuthorityCreateProblem(AdminValidationProblem):
    pass


class AdminAuthorityCreateResult(graphene.Union):
    class Meta:
        types = (
            AdminAuthorityCreateSuccess,
            AdminAuthorityCreateProblem,
        )


class AdminAuthorityUpdateSuccess(graphene.ObjectType):
    authority = graphene.Field(AuthorityType)


class AdminAuthorityUpdateProblem(AdminValidationProblem):
    pass


class AdminAuthorityUpdateResult(graphene.Union):
    class Meta:
        types = (
            AdminAuthorityUpdateSuccess,
            AdminAuthorityUpdateProblem,
        )


class AdminAuthorityUserCreateSuccess(DjangoObjectType):
    class Meta:
        model = AuthorityUser


class AdminAuthorityUserCreateProblem(AdminValidationProblem):
    pass


class AdminAuthorityUserUpdateSuccess(graphene.ObjectType):
    authority_user = graphene.Field(AuthorityUserType)


class AdminAuthorityUserUpdateProblem(AdminValidationProblem):
    pass


class AdminAuthorityUserCreateResult(graphene.Union):
    class Meta:
        types = (
            AdminAuthorityUserCreateSuccess,
            AdminAuthorityUserCreateProblem,
        )


class AdminAuthorityUserUpdateResult(graphene.Union):
    class Meta:
        types = (
            AdminAuthorityUserUpdateSuccess,
            AdminAuthorityUserUpdateProblem,
        )


## Invitation Code
class AdminInvitationCodeCreateSuccess(DjangoObjectType):
    class Meta:
        model = InvitationCode


class AdminInvitationCodeCreateProblem(AdminValidationProblem):
    pass


class AdminInvitationCodeCreateResult(graphene.Union):
    class Meta:
        types = (
            AdminInvitationCodeCreateSuccess,
            AdminInvitationCodeCreateProblem,
        )


class AdminInvitationCodeUpdateSuccess(graphene.ObjectType):
    invitation_code = graphene.Field(InvitationCodeType)


class AdminInvitationCodeUpdateProblem(AdminValidationProblem):
    pass


class AdminInvitationCodeUpdateResult(graphene.Union):
    class Meta:
        types = (
            AdminInvitationCodeUpdateSuccess,
            AdminInvitationCodeUpdateProblem,
        )
