from calendar import timegm

import graphene
from django.conf import settings
from django.utils import timezone
from django.utils.timezone import now
from graphql import GraphQLError
from graphql_jwt.decorators import login_required
from graphql_jwt.utils import jwt_encode
from django.db import connection

from accounts.models import (
    AuthorityUser,
    InvitationCode,
    Feature,
    Authority,
    Configuration,
    Place,
    Village,
    AnimalSpecies,
    CensusDefinition,
    CensusDefinitionVersion,
    CurrentAnimalCensusFact,
    CurrentHumanCensusFact,
    VillageCensusSnapshot,
    VillageReporterAssignment,
)
from accounts.schema.types import (
    AdminConfigurationQueryType,
    AdminInvitationCodeQueryType,
    AuthorityUserType,
    InvitationCodeType,
    PlaceType,
    UserProfileType,
    FeatureType,
    AuthorityType,
    AdminVillageQueryType,
    AdminAuthorityQueryType,
    AdminAuthorityUserQueryType,
    AdminAuthorityInheritLookupType,
    LoginQrTokenType,
    ConfigurationType,
    AdminPlaceQueryType,
    AdminAnimalSpeciesQueryType,
    AnimalSpeciesType,
    CensusDefinitionType,
    CensusDefinitionVersionType,
    CensusKindSummaryType,
    CurrentAnimalCensusFactType,
    CurrentHumanCensusFactType,
    VillageCensusSnapshotType,
)
from accounts.schema.types import CheckInvitationCodeType
from accounts.utils import filter_authority_permission
from accounts.animal_census_capability import is_animal_census_capability_enabled
from accounts.village_capability import is_village_capability_enabled
from pagination import DjangoPaginationConnectionField


class Query(graphene.ObjectType):
    me = graphene.Field(UserProfileType)
    check_invitation_code = graphene.Field(
        CheckInvitationCodeType, code=graphene.String(required=True)
    )
    features = graphene.List(FeatureType)
    configurations = graphene.List(ConfigurationType)
    authorities = DjangoPaginationConnectionField(AuthorityType)
    authority = graphene.Field(AuthorityType, id=graphene.ID(required=True))
    authority_inherits_down = graphene.List(
        graphene.NonNull(AuthorityType), authority_id=graphene.ID(required=True)
    )
    authority_inherits_down_shallow = graphene.List(
        graphene.NonNull(AuthorityType), authority_id=graphene.ID(required=True)
    )
    admin_authority_get = graphene.Field(
        AdminAuthorityQueryType, id=graphene.ID(required=True)
    )
    admin_authority_query = DjangoPaginationConnectionField(AdminAuthorityQueryType)
    admin_authority_inherit_lookup = DjangoPaginationConnectionField(
        AdminAuthorityInheritLookupType
    )
    admin_authority_user_query = DjangoPaginationConnectionField(
        AdminAuthorityUserQueryType
    )
    admin_invitation_code_query = DjangoPaginationConnectionField(
        AdminInvitationCodeQueryType
    )
    admin_place_query = DjangoPaginationConnectionField(AdminPlaceQueryType)
    admin_village_query = DjangoPaginationConnectionField(AdminVillageQueryType)
    admin_animal_species_query = DjangoPaginationConnectionField(
        AdminAnimalSpeciesQueryType
    )
    animal_species = graphene.List(AnimalSpeciesType)
    census_definitions = graphene.List(CensusDefinitionType)
    active_census_definition_version = graphene.Field(
        CensusDefinitionVersionType, kind=graphene.String(required=True)
    )
    active_village_census_definitions = graphene.List(
        CensusKindSummaryType, village_id=graphene.Int(required=True)
    )
    latest_village_census = graphene.Field(
        VillageCensusSnapshotType, village_id=graphene.Int(required=True)
    )
    latest_village_census_v2 = graphene.Field(
        VillageCensusSnapshotType,
        village_id=graphene.Int(required=True),
        kind=graphene.String(required=True),
    )
    current_animal_census_facts = graphene.List(
        CurrentAnimalCensusFactType, village_id=graphene.Int(required=True)
    )
    current_human_census_facts = graphene.List(
        CurrentHumanCensusFactType, village_id=graphene.Int(required=True)
    )
    place_get = graphene.Field(PlaceType, id=graphene.Int(required=True))

    invitation_code = graphene.Field(InvitationCodeType, id=graphene.ID(required=True))
    authority_user = graphene.Field(AuthorityUserType, id=graphene.ID(required=True))

    admin_configuration_query = DjangoPaginationConnectionField(
        AdminConfigurationQueryType
    )
    configuration_get = graphene.Field(
        ConfigurationType, key=graphene.String(required=True)
    )
    village_capability_enabled = graphene.Boolean(required=True)
    animal_census_capability_enabled = graphene.Boolean(required=True)

    get_login_qr_token = graphene.Field(
        LoginQrTokenType, user_id=graphene.ID(required=True)
    )

    @staticmethod
    @login_required
    def resolve_me(root, info):
        user = info.context.user
        if user.is_authority_user:
            return user.authorityuser
        return user

    @staticmethod
    def resolve_check_invitation_code(root, info, code):
        invitation = InvitationCode.objects.filter(
            code=code, from_date__lte=now(), through_date__gte=now()
        ).first()
        if invitation:
            # if auto_generate_username is True, return generated username
            auto_generate_username = False
            try:
                config = Configuration.objects.get(
                    key="features.auto_generate_username"
                )
                if config.value == "enable":
                    auto_generate_username = True

            except Configuration.DoesNotExist:
                pass

            if auto_generate_username:
                # use db sequence to generate username
                with connection.cursor() as cursor:
                    cursor = connection.cursor()
                    cursor.execute(
                        "SELECT nextval('accounts_authorityuser_username_seq')"
                    )
                    row = cursor.fetchone()
                    generated_username = f"u{row[0]}"

                info.context.__dict__["generated_username"] = generated_username

            # if auto_generate_email is True, return generated email
            auto_generate_email = False
            try:
                config = Configuration.objects.get(key="features.auto_generate_email")
                if config.value == "enable":
                    auto_generate_email = True

            except Configuration.DoesNotExist:
                pass

            if auto_generate_email:
                # if username was already generated, use it for email
                if "generated_username" in info.context.__dict__:
                    generated_username = info.context.__dict__["generated_username"]
                    generated_email = f"{generated_username}@generated.ohtk.org"
                    info.context.__dict__["generated_email"] = generated_email
                else:
                    # use db sequence to generate email
                    with connection.cursor() as cursor:
                        cursor = connection.cursor()
                        cursor.execute(
                            "SELECT nextval('accounts_authorityuser_username_seq')"
                        )
                        row = cursor.fetchone()
                        generated_email = f"u{row[0]}"

                    generated_email = f"{generated_email}@generated.ohtk.org"
                    info.context.__dict__["generated_email"] = generated_email

            return invitation
        raise GraphQLError(f"code {code} not found!")

    @staticmethod
    def resolve_features(root, info):
        return Feature.objects.all()

    @staticmethod
    def resolve_configurations(root, info):
        return Configuration.objects.filter(key__startswith="mobile")

    @staticmethod
    @login_required
    def resolve_authorities(root, info, **kwargs):
        user = info.context.user
        if not user.is_superuser:
            raise GraphQLError("Permission denied.")
        return Authority.objects.all()

    @staticmethod
    @login_required
    def resolve_authority_inherits_down(root, info, authority_id):
        return Authority.objects.get(id=authority_id).all_inherits_down()

    @staticmethod
    @login_required
    def resolve_authority_inherits_down_shallow(root, info, authority_id):
        return Authority.objects.get(id=authority_id).inherits_down_shallow()

    @staticmethod
    @login_required
    def resolve_authority(root, info, id):
        user = info.context.user
        if not user.is_superuser:
            raise GraphQLError("Permission denied.")
        return Authority.objects.get(id=id)

    @staticmethod
    @login_required
    def resolve_admin_authority_get(root, info, id):
        user = info.context.user
        if not user.is_superuser:
            raise GraphQLError("Permission denied.")
        return Authority.objects.get(id=id)

    @staticmethod
    @login_required
    def resolve_authority_user(root, info, id):
        user = info.context.user
        query = AuthorityUser.objects.all()
        query = filter_authority_permission(user, query)
        return query.get(id=id)

    @staticmethod
    @login_required
    def resolve_invitation_code(root, info, id):
        user = info.context.user
        query = InvitationCode.objects.all()
        query = filter_authority_permission(user, query)
        return query.get(id=id)

    @staticmethod
    @login_required
    def resolve_get_login_qr_token(root, info, user_id):
        user = info.context.user
        if not (user.is_authority_user or user.is_superuser):
            raise GraphQLError("Permission denied.")

        target_user = AuthorityUser.objects.get(id=user_id)
        if target_user.role != AuthorityUser.Role.REPORTER:
            raise GraphQLError("Permission denied.")

        exp = timezone.now() + settings.QR_CODE_LOGIN_EXPIRATION_DAYS
        payload = {
            "username": target_user.username,
            "domain": info.context.tenant.domain_url,
            "exp": timegm(exp.utctimetuple()),
        }

        token = jwt_encode(payload, info.context)

        return {
            "token": token,
        }

    @staticmethod
    @login_required
    def resolve_place_get(root, info, id):
        return Place.objects.get(id=id)

    @staticmethod
    @login_required
    def resolve_configuration_get(root, info, key):
        return Configuration.objects.get(key=key)

    @staticmethod
    @login_required
    def resolve_village_capability_enabled(root, info):
        return is_village_capability_enabled()

    @staticmethod
    @login_required
    def resolve_animal_census_capability_enabled(root, info):
        return is_animal_census_capability_enabled()

    @staticmethod
    @login_required
    def resolve_admin_place_query(root, info, **kwargs):
        user = info.context.user
        query = Place.objects.all()
        if not user.is_superuser:
            if user.is_authority_user:
                if user.is_authority_role_in([AuthorityUser.Role.ADMIN]):
                    query = query.filter(
                        authority__in=user.authorityuser.authority.all_inherits_down()
                    )
                elif user.is_authority_role_in([AuthorityUser.Role.OFFICER]):
                    query = query.filter(authority=user.authorityuser.authority)
                else:
                    raise GraphQLError("Permission denied.")
        return query

    @staticmethod
    @login_required
    def resolve_admin_village_query(root, info, **kwargs):
        if not is_village_capability_enabled():
            return Village.objects.none()

        user = info.context.user
        query = Village.objects.all()
        query = filter_authority_permission(user, query)
        return query

    @staticmethod
    @login_required
    def resolve_admin_animal_species_query(root, info, **kwargs):
        user = info.context.user
        if not user.is_superuser:
            raise GraphQLError("Permission denied.")
        return AnimalSpecies.objects.all()

    @staticmethod
    @login_required
    def resolve_animal_species(root, info):
        if not (
            is_village_capability_enabled() and is_animal_census_capability_enabled()
        ):
            return AnimalSpecies.objects.none()
        return AnimalSpecies.objects.filter(active=True).order_by("sort_order", "code")

    @staticmethod
    @login_required
    def resolve_census_definitions(root, info):
        if not (
            is_village_capability_enabled() and is_animal_census_capability_enabled()
        ):
            return CensusDefinition.objects.none()
        return CensusDefinition.objects.filter(enabled=True).order_by(
            "sort_order", "kind"
        )

    @staticmethod
    @login_required
    def resolve_active_census_definition_version(root, info, kind):
        if not (
            is_village_capability_enabled() and is_animal_census_capability_enabled()
        ):
            return None
        return (
            CensusDefinitionVersion.objects.select_related("definition")
            .filter(
                definition__kind=kind,
                definition__enabled=True,
                status=CensusDefinitionVersion.Status.PUBLISHED,
            )
            .order_by("-version")
            .first()
        )

    @staticmethod
    @login_required
    def resolve_active_village_census_definitions(root, info, village_id):
        if not (
            is_village_capability_enabled() and is_animal_census_capability_enabled()
        ):
            return []

        village = _get_permitted_census_village(info, village_id)
        if village is None:
            return []

        definitions = CensusDefinition.objects.filter(enabled=True).order_by(
            "sort_order", "kind"
        )
        summaries = []
        for definition in definitions:
            active_version = (
                definition.versions.filter(
                    status=CensusDefinitionVersion.Status.PUBLISHED
                )
                .order_by("-version")
                .first()
            )
            if active_version is None:
                continue

            latest_snapshot = (
                VillageCensusSnapshot.objects.filter(
                    village=village, definition_version__definition=definition
                )
                .order_by("-census_date", "-created_at")
                .first()
            )
            summaries.append(
                CensusKindSummaryType(
                    kind=definition.kind,
                    name=_census_kind_name(definition.kind),
                    enabled=definition.enabled,
                    active_version=active_version,
                    latest_snapshot=latest_snapshot,
                )
            )
        return summaries

    @staticmethod
    @login_required
    def resolve_latest_village_census(root, info, village_id):
        if not (
            is_village_capability_enabled() and is_animal_census_capability_enabled()
        ):
            return None

        village = _get_permitted_census_village(info, village_id)
        if village is None:
            return None

        return (
            VillageCensusSnapshot.objects.filter(village=village)
            .order_by("-census_date", "-created_at")
            .first()
        )

    @staticmethod
    @login_required
    def resolve_latest_village_census_v2(root, info, village_id, kind):
        if not (
            is_village_capability_enabled() and is_animal_census_capability_enabled()
        ):
            return None

        village = _get_permitted_census_village(info, village_id)
        if village is None:
            return None

        return (
            VillageCensusSnapshot.objects.filter(
                village=village, definition_version__definition__kind=kind
            )
            .order_by("-census_date", "-created_at")
            .first()
        )

    @staticmethod
    @login_required
    def resolve_current_animal_census_facts(root, info, village_id):
        return CurrentAnimalCensusFact.objects.filter(
            fact__snapshot__village_id=village_id
        ).select_related("fact", "fact__animal_species")

    @staticmethod
    @login_required
    def resolve_current_human_census_facts(root, info, village_id):
        return CurrentHumanCensusFact.objects.filter(
            fact__snapshot__village_id=village_id
        ).select_related("fact")


def _get_permitted_census_village(info, village_id):
    user = info.context.user
    try:
        village = Village.objects.get(pk=village_id)
    except Village.DoesNotExist:
        return None

    if user.is_superuser:
        return village
    if user.is_authority_role_in([AuthorityUser.Role.ADMIN]):
        if user.authorityuser.authority.is_in_inherits_down([village.authority_id]):
            return village
        raise GraphQLError("Permission denied.")
    if user.is_authority_role_in([AuthorityUser.Role.OFFICER]):
        if user.authorityuser.authority_id == village.authority_id:
            return village
        raise GraphQLError("Permission denied.")
    if user.is_authority_role_in([AuthorityUser.Role.REPORTER]):
        if VillageReporterAssignment.objects.filter(
            reporter=user.authorityuser, village=village
        ).exists():
            return village
        raise GraphQLError("Permission denied.")
    raise GraphQLError("Permission denied.")


def _census_kind_name(kind):
    if kind == CensusDefinition.Kind.ANIMAL:
        return "Animal census"
    if kind == CensusDefinition.Kind.HUMAN:
        return "Human census"
    return f"{kind.title()} census"
