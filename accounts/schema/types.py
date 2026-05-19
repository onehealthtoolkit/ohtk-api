import graphene
import django_filters
from django.db.models import Q
from easy_thumbnails.files import get_thumbnailer
from graphene_django import DjangoObjectType
from graphene.types.generic import GenericScalar

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
    Village,
    AnimalSpecies,
    VillageCensusSnapshot,
    AnimalCensusFact,
    CensusDefinition,
    CensusDefinitionVersion,
    CurrentAnimalCensusFact,
    CurrentHumanCensusFact,
    HumanCensusFact,
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


class NumberInFilter(django_filters.BaseInFilter, django_filters.NumberFilter):
    pass


class AdminAuthorityUserQueryFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(method="filter_q")
    authorities = NumberInFilter(field_name="authority__id", lookup_expr="in")
    role = django_filters.CharFilter(lookup_expr="exact")
    date_joined_lte = django_filters.DateTimeFilter(
        field_name="date_joined", lookup_expr="lte"
    )
    date_joined_gte = django_filters.DateTimeFilter(
        field_name="date_joined", lookup_expr="gte"
    )

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
            | Q(telephone__icontains=value)
        )

    def filter_role(self, queryset, name, value):
        return queryset.filter(role__exact=value)


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
            "telephone",
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
        queryset = queryset.filter(is_active=True).prefetch_related("authority")

        return queryset


class AdminInvitationCodeQueryType(DjangoObjectType):
    class Meta:
        model = InvitationCode
        fields = (
            "id",
            "code",
            "authority",
            "villages",
            "from_date",
            "through_date",
            "role",
        )
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
        fields = (
            "id",
            "authority",
            "villages",
            "code",
            "from_date",
            "through_date",
            "role",
        )


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
    assigned_villages = graphene.List(lambda: VillageType)

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
            "address",
            "role",
        )

    def resolve_assigned_villages(self, info):
        return Village.objects.filter(reporter_assignments__reporter=self).distinct()


class VillageType(DjangoObjectType):
    latitude = graphene.Float()
    longitude = graphene.Float()

    class Meta:
        model = Village
        fields = ("id", "code", "name", "authority", "location", "active")

    def resolve_latitude(self, info):
        if self.location:
            return self.location.y
        return None

    def resolve_longitude(self, info):
        if self.location:
            return self.location.x
        return None


class UserProfileType(graphene.ObjectType):
    id = graphene.Int(required=True)
    username = graphene.String(required=True)
    first_name = graphene.String(required=True)
    last_name = graphene.String(required=True)
    telephone = graphene.String(required=False)
    email = graphene.String()
    address = graphene.String(required=False)
    authority_name = graphene.String(required=False)
    authority_id = graphene.Int(required=False)
    avatar_url = graphene.String(required=False)
    is_staff = graphene.Boolean()
    is_superuser = graphene.Boolean()
    role = graphene.String()
    consent = graphene.Boolean()
    features = graphene.List(graphene.String)
    assigned_villages = graphene.List(VillageType)

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

    def resolve_assigned_villages(self, info):
        if self.is_authority_user:
            return Village.objects.filter(reporter_assignments__reporter=self).distinct()
        return []


class CheckInvitationCodeType(DjangoObjectType):
    generated_username = graphene.String(required=False)
    generated_email = graphene.String(required=False)

    class Meta:
        model = InvitationCode
        fields = ("code", "authority", "villages")

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
        fields = "__all__"


class ConfigurationType(DjangoObjectType):
    class Meta:
        model = Configuration
        fields = "__all__"


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
        fields = "__all__"


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
        fields = "__all__"


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
        fields = "__all__"


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
        fields = "__all__"


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
        fields = "__all__"

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


class AdminVillageQueryFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(method="filter_q")
    authority_id = django_filters.NumberFilter(field_name="authority__id")
    active = django_filters.BooleanFilter()

    class Meta:
        model = Village
        fields = ["authority_id", "active"]

    def filter_q(self, queryset, name, value):
        return queryset.filter(Q(name__icontains=value) | Q(code__icontains=value))


class AdminVillageQueryType(DjangoObjectType):
    latitude = graphene.Float()
    longitude = graphene.Float()

    class Meta:
        model = Village
        fields = ("id", "code", "name", "authority", "location", "active")
        filterset_class = AdminVillageQueryFilter

    def resolve_latitude(self, info):
        if self.location:
            return self.location.y
        return None

    def resolve_longitude(self, info):
        if self.location:
            return self.location.x
        return None


class AdminVillageCreateSuccess(DjangoObjectType):
    latitude = graphene.Float()
    longitude = graphene.Float()

    class Meta:
        model = Village
        fields = "__all__"

    def resolve_latitude(self, info):
        if self.location:
            return self.location.y
        return None

    def resolve_longitude(self, info):
        if self.location:
            return self.location.x
        return None


class AdminVillageCreateProblem(AdminValidationProblem):
    pass


class AdminVillageCreateResult(graphene.Union):
    class Meta:
        types = (AdminVillageCreateSuccess, AdminVillageCreateProblem)


class AdminVillageUpdateSuccess(DjangoObjectType):
    latitude = graphene.Float()
    longitude = graphene.Float()

    class Meta:
        model = Village
        fields = "__all__"

    def resolve_latitude(self, info):
        if self.location:
            return self.location.y
        return None

    def resolve_longitude(self, info):
        if self.location:
            return self.location.x
        return None


class AdminVillageUpdateProblem(AdminValidationProblem):
    pass


class AdminVillageUpdateResult(graphene.Union):
    class Meta:
        types = (AdminVillageUpdateSuccess, AdminVillageUpdateProblem)


class AdminAnimalSpeciesQueryFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(method="filter_q")
    active = django_filters.BooleanFilter()

    class Meta:
        model = AnimalSpecies
        fields = ["active"]

    def filter_q(self, queryset, name, value):
        return queryset.filter(Q(name__icontains=value) | Q(code__icontains=value))


class AnimalSpeciesType(DjangoObjectType):
    class Meta:
        model = AnimalSpecies
        fields = ("id", "code", "name", "active", "sort_order")


class AdminAnimalSpeciesQueryType(DjangoObjectType):
    class Meta:
        model = AnimalSpecies
        fields = ("id", "code", "name", "active", "sort_order")
        filterset_class = AdminAnimalSpeciesQueryFilter


class AdminAnimalSpeciesCreateSuccess(DjangoObjectType):
    class Meta:
        model = AnimalSpecies
        fields = "__all__"


class AdminAnimalSpeciesCreateProblem(AdminValidationProblem):
    pass


class AdminAnimalSpeciesCreateResult(graphene.Union):
    class Meta:
        types = (AdminAnimalSpeciesCreateSuccess, AdminAnimalSpeciesCreateProblem)


class AdminAnimalSpeciesUpdateSuccess(DjangoObjectType):
    class Meta:
        model = AnimalSpecies
        fields = "__all__"


class AdminAnimalSpeciesUpdateProblem(AdminValidationProblem):
    pass


class AdminAnimalSpeciesUpdateResult(graphene.Union):
    class Meta:
        types = (AdminAnimalSpeciesUpdateSuccess, AdminAnimalSpeciesUpdateProblem)


class AnimalCensusFactType(DjangoObjectType):
    species = graphene.Field(AnimalSpeciesType)
    animal_quantity = graphene.Int()
    household_quantity = graphene.Int()
    extra_dimensions = GenericScalar()
    measures = GenericScalar()

    class Meta:
        model = AnimalCensusFact
        fields = (
            "id",
            "animal_species",
            "row_key",
            "extra_dimensions",
            "measures",
        )

    def resolve_species(self, info):
        return self.animal_species

    def resolve_animal_quantity(self, info):
        return self.measures.get("animal_quantity", 0)

    def resolve_household_quantity(self, info):
        return self.measures.get("household_quantity", 0)


class CensusDefinitionType(DjangoObjectType):
    class Meta:
        model = CensusDefinition
        fields = ("id", "kind", "enabled", "sort_order")


class CensusDefinitionVersionType(DjangoObjectType):
    schema = GenericScalar()
    runtime_schema = GenericScalar()

    class Meta:
        model = CensusDefinitionVersion
        fields = (
            "id",
            "definition",
            "version",
            "status",
            "schema",
            "published_at",
        )

    def resolve_runtime_schema(self, info):
        schema = dict(self.schema or {})
        if self.definition.kind == CensusDefinition.Kind.ANIMAL:
            schema["rows"] = [
                {
                    "species_id": species.id,
                    "species_code": species.code,
                    "label": species.name,
                    "row_key": f"species:{species.code}",
                }
                for species in AnimalSpecies.objects.filter(active=True).order_by(
                    "sort_order", "code"
                )
            ]
        return schema


class HumanCensusFactType(DjangoObjectType):
    dimensions = GenericScalar()
    measures = GenericScalar()

    class Meta:
        model = HumanCensusFact
        fields = ("id", "row_key", "dimensions", "measures")


class CurrentAnimalCensusFactType(DjangoObjectType):
    class Meta:
        model = CurrentAnimalCensusFact
        fields = ("id", "fact", "updated_at")


class CurrentHumanCensusFactType(DjangoObjectType):
    class Meta:
        model = CurrentHumanCensusFact
        fields = ("id", "fact", "updated_at")


class VillageCensusSnapshotType(DjangoObjectType):
    form_data = GenericScalar()

    class Meta:
        model = VillageCensusSnapshot
        fields = (
            "id",
            "village",
            "reporter",
            "definition_version",
            "census_date",
            "form_data",
            "status",
            "submitted_at",
            "facts",
            "human_facts",
        )


class VillageCensusSnapshotProblem(AdminValidationProblem):
    pass


class VillageCensusSnapshotResult(graphene.Union):
    class Meta:
        types = (VillageCensusSnapshotType, VillageCensusSnapshotProblem)


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
        fields = "__all__"


class AdminConfigurationCreateProblem(AdminValidationProblem):
    pass


class AdminConfigurationCreateResult(graphene.Union):
    class Meta:
        types = (AdminConfigurationCreateSuccess, AdminConfigurationCreateProblem)


class AdminConfigurationUpdateSuccess(DjangoObjectType):
    class Meta:
        model = Configuration
        fields = "__all__"


class AdminConfigurationUpdateProblem(AdminValidationProblem):
    pass


class AdminConfigurationUpdateResult(graphene.Union):
    class Meta:
        types = (AdminConfigurationUpdateSuccess, AdminConfigurationUpdateProblem)
