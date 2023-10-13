import graphene
import django_filters
from django.db.models import Q
from easy_thumbnails.files import get_thumbnailer
from graphene_django import DjangoObjectType

from django.contrib.gis.db import models
from graphene_django.converter import convert_django_field
from graphql import GraphQLError

from accounts.models import (
    Authority,
    AuthorityUser,
    InvitationCode,
    Feature,
    User,
    Configuration,
    Place,
)
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


class AuthorityBoundaryConnectType(DjangoObjectType):
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
    boundary_connects = graphene.List(AuthorityBoundaryConnectType, required=True)

    def resolve_inherits(self, info, **kwargs):
        results = []
        for authority in self.inherits.all():
            results.append(authority)
        return results

    def resolve_boundary_connects(self, info, **kwargs):
        results = []
        for authority in self.boundary_connects.all():
            results.append(authority)
        return results


class AdminAuthorityQueryFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(
        method="filter_q",
        label="Search",
    )

    class Meta:
        model = Authority
        fields = ["q"]

    def filter_q(self, queryset, name, value):
        return queryset.filter(Q(name__icontains=value) | Q(code__icontains=value))


class AdminAuthorityQueryType(DjangoObjectType):
    class Meta:
        model = Authority
        fields = (
            "id",
            "code",
            "name",
        )
        filterset_class = AdminAuthorityQueryFilter


class AdminAuthorityInheritLookupFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(
        method="filter_q",
        label="Search",
    )

    class Meta:
        model = Authority
        fields = ["q"]

    def filter_q(self, queryset, name, value):
        return queryset.filter(Q(name__icontains=value) | Q(code__icontains=value))


class AdminAuthorityInheritLookupType(DjangoObjectType):
    class Meta:
        model = Authority
        fields = (
            "id",
            "code",
            "name",
        )
        filterset_class = AdminAuthorityInheritLookupFilter


class AdminAuthorityUserQueryFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(method="filter_q")

    class Meta:
        model = AuthorityUser
        fields = []

    def filter_q(self, queryset, name, value):
        return queryset.filter(
            Q(first_name__icontains=value)
            | Q(last_name__icontains=value)
            | Q(username__icontains=value)
            | Q(email__icontains=value)
            | Q(authority__name__icontains=value)
        )


class AdminAuthorityUserQueryType(DjangoObjectType):
    class Meta:
        model = AuthorityUser
        fields = (
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "role",
            "authority",
        )
        filterset_class = AdminAuthorityUserQueryFilter

    @classmethod
    def get_queryset(cls, queryset, info):
        user = info.context.user
        if user.is_authority_role_in([AuthorityUser.Role.OFFICER]):
            queryset = queryset.filter(authority_id=user.authorityuser.authority)
        elif user.is_authority_role_in([AuthorityUser.Role.ADMIN]):
            queryset = queryset.filter(
                authority_id__in=user.authorityuser.authority.all_inherits_down()
            )
        elif user.is_authority_role_in([AuthorityUser.Role.REPORTER]):
            raise GraphQLError("Permission denied")
        queryset.prefetch_related("authority")
        return queryset


class AdminInvitationCodeQueryType(DjangoObjectType):
    class Meta:
        model = InvitationCode
        fields = ("id", "code", "authority", "from_date", "through_date", "role")
        filter_fields = {
            "role": ["contains", "istartswith", "exact"],
        }

    @classmethod
    def get_queryset(cls, queryset, info):
        user = info.context.user
        if user.is_authority_role_in([AuthorityUser.Role.OFFICER]):
            queryset = queryset.filter(authority_id=user.authorityuser.authority)
        elif user.is_authority_role_in([AuthorityUser.Role.ADMIN]):
            queryset = queryset.filter(
                authority_id__in=user.authorityuser.authority.all_inherits_down()
            )
        elif user.is_authority_role_in([AuthorityUser.Role.REPORTER]):
            raise GraphQLError("Permission denied")
        return queryset


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
            return get_thumbnailer(self.avatar)["thumbnail"].url
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
    telephone = graphene.String(required=False)
    email = graphene.String()
    authority_name = graphene.String(required=False)
    authority_id = graphene.Int(required=False)
    avatar_url = graphene.String(required=False)
    is_staff = graphene.Boolean()
    is_superuser = graphene.Boolean()
    role = graphene.String()
    consent = graphene.Boolean()
    features = graphene.List(graphene.String)

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
            return get_thumbnailer(self.avatar)["thumbnail"].url
        else:
            return None

    def resolve_consent(self, info):
        if self.is_authority_user:
            return self.consent
        else:
            return True

    def resolve_features(self, info):
        return [
            configuration.key
            for configuration in Configuration.objects.filter(
                key__startswith="features.", value="enable"
            ).all()
        ]


class CheckInvitationCodeType(DjangoObjectType):
    generated_username = graphene.String(required=False)
    generated_email = graphene.String(required=False)

    class Meta:
        model = InvitationCode
        fields = ("code", "authority")

    def resolve_generated_username(self, info):
        if "generated_username" in info.context.__dict__:
            return info.context.__dict__["generated_username"]
        return None

    def resolve_generated_email(self, info):
        if "generated_email" in info.context.__dict__:
            return info.context.__dict__["generated_email"]
        return None


class FeatureType(DjangoObjectType):
    class Meta:
        model = Feature


class ConfigurationType(DjangoObjectType):
    class Meta:
        model = Configuration


class PlaceType(DjangoObjectType):
    latitude = graphene.Float()
    longitude = graphene.Float()

    class Meta:
        model = Place
        fields = (
            "id",
            "name",
            "location",
            "authority",
            "notification_to",
        )

    def resolve_latitude(self, info):
        if self.location:
            return self.location.y
        else:
            return None

    def resolve_longitude(self, info):
        if self.location:
            return self.location.x
        else:
            return None


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


class LoginQrTokenType(graphene.ObjectType):
    token = graphene.String(required=True)


class AdminPlaceQueryFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(method="filter_q")

    class Meta:
        model = Place
        fields = []

    def filter_q(self, queryset, name, value):
        return queryset.filter(Q(name__icontains=value))


class AdminPlaceQueryType(DjangoObjectType):
    class Meta:
        model = Place
        fields = ("id", "name", "authority", "notification_to")
        filterset_class = AdminPlaceQueryFilter


class AdminPlaceCreateSuccess(DjangoObjectType):
    class Meta:
        model = Place


class AdminPlaceCreateProblem(AdminValidationProblem):
    pass


class AdminPlaceCreateResult(graphene.Union):
    class Meta:
        types = (AdminPlaceCreateSuccess, AdminPlaceCreateProblem)


class AdminPlaceUpdateSuccess(DjangoObjectType):
    latitude = graphene.Float()
    longitude = graphene.Float()

    class Meta:
        model = Place

    def resolve_latitude(self, info):
        if self.location:
            return self.location.y
        else:
            return None

    def resolve_longitude(self, info):
        if self.location:
            return self.location.x
        else:
            return None


class AdminPlaceUpdateProblem(AdminValidationProblem):
    pass


class AdminPlaceUpdateResult(graphene.Union):
    class Meta:
        types = (AdminPlaceUpdateSuccess, AdminPlaceUpdateProblem)


class AdminConfigurationQueryFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(method="filter_q")

    class Meta:
        model = Configuration
        fields = []

    def filter_q(self, queryset, name, value):
        return queryset.filter(Q(key__icontains=value))


class AdminConfigurationQueryType(DjangoObjectType):
    class Meta:
        model = Configuration
        fields = ("key", "value")
        filterset_class = AdminConfigurationQueryFilter


class AdminConfigurationCreateSuccess(DjangoObjectType):
    class Meta:
        model = Configuration


class AdminConfigurationCreateProblem(AdminValidationProblem):
    pass


class AdminConfigurationCreateResult(graphene.Union):
    class Meta:
        types = (AdminConfigurationCreateSuccess, AdminConfigurationCreateProblem)


class AdminConfigurationUpdateSuccess(DjangoObjectType):
    class Meta:
        model = Configuration


class AdminConfigurationUpdateProblem(AdminValidationProblem):
    pass


class AdminConfigurationUpdateResult(graphene.Union):
    class Meta:
        types = (AdminConfigurationUpdateSuccess, AdminConfigurationUpdateProblem)
