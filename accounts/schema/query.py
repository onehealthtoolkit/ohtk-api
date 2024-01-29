from calendar import timegm
from datetime import datetime

import graphene
from django.conf import settings
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
    AdminAuthorityQueryType,
    AdminAuthorityUserQueryType,
    AdminAuthorityInheritLookupType,
    LoginQrTokenType,
    ConfigurationType,
    AdminPlaceQueryType,
)
from accounts.schema.types import CheckInvitationCodeType
from accounts.utils import filter_authority_permission
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
    place_get = graphene.Field(PlaceType, id=graphene.Int(required=True))

    invitation_code = graphene.Field(InvitationCodeType, id=graphene.ID(required=True))
    authority_user = graphene.Field(AuthorityUserType, id=graphene.ID(required=True))

    admin_configuration_query = DjangoPaginationConnectionField(
        AdminConfigurationQueryType
    )
    configuration_get = graphene.Field(
        ConfigurationType, key=graphene.String(required=True)
    )

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

        exp = datetime.utcnow() + settings.QR_CODE_LOGIN_EXPIRATION_DAYS
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
