from attr import fields
import graphene
from django.conf import settings
from django.utils.timezone import now
from graphql import GraphQLError
from graphql_jwt.decorators import login_required
from graphql_jwt.refresh_token.shortcuts import create_refresh_token
from graphql_jwt.shortcuts import get_token
from pkg_resources import require

from accounts.models import InvitationCode, AuthorityUser, Feature, Authority
from accounts.types import (
    AdminAuthorityCreateProblem,
    AdminAuthorityCreateResult,
    AdminAuthorityQueryType,
    AdminFieldValidationProblem,
    UserProfileType,
    CheckInvitationCodeType,
    FeatureType,
    AuthorityType,
)
from pagination import DjangoPaginationConnectionField


class Query(graphene.ObjectType):
    me = graphene.Field(UserProfileType)
    check_invitation_code = graphene.Field(
        CheckInvitationCodeType, code=graphene.String(required=True)
    )
    features = graphene.List(FeatureType)
    authorities = DjangoPaginationConnectionField(AuthorityType)
    adminAuthorityQuery = DjangoPaginationConnectionField(AdminAuthorityQueryType)

    @staticmethod
    @login_required
    def resolve_me(root, info):
        user = info.context.user
        if hasattr(user, "authorityuser"):
            return user.authorityuser
        return user

    @staticmethod
    def resolve_check_invitation_code(root, info, code):
        invitation = InvitationCode.objects.filter(
            code=code, from_date__lte=now(), through_date__gte=now()
        ).first()
        if invitation:
            return invitation
        raise GraphQLError(f"code {code} not found!")

    @staticmethod
    def resolve_features(root, info):
        return Feature.objects.all()

    @staticmethod
    def resolve_authorities(root, info, **kwargs):
        user = info.context.user
        if not user.is_superuser:
            raise GraphQLError("Permission denied.")
        return Authority.objects.all()


class AdminAuthorityCreateMutation(graphene.Mutation):
    class Arguments:
        code = graphene.String(required=True)
        name = graphene.String(required=True)

    result = graphene.Field(AdminAuthorityCreateResult)

    @staticmethod
    def mutate(root, info, code, name):
        if Authority.objects.filter(code=code).exists():
            return AdminAuthorityCreateMutation(
                result=AdminAuthorityCreateProblem(
                    fields=[
                        AdminFieldValidationProblem(
                            name="code", message="duplicate code"
                        )
                    ]
                )
            )

        if not name:
            return AdminAuthorityCreateMutation(
                result=AdminAuthorityCreateProblem(
                    fields=[
                        AdminFieldValidationProblem(
                            name="name", message="name must not be empty"
                        )
                    ]
                )
            )

        authority = Authority.objects.create(code=code, name=name)
        return AdminAuthorityCreateMutation(result=authority)


class AuthorityUserRegisterMutation(graphene.Mutation):
    class Arguments:
        invitation_code = graphene.String(required=True)
        username = graphene.String(required=True)
        first_name = graphene.String(required=True)
        last_name = graphene.String(required=True)
        telephone = graphene.String(required=False)
        email = graphene.String(required=True)

    me = graphene.Field(UserProfileType)
    # return only when enable FEATURES.AUTO_LOGIN_AFTER_REGISTER
    token = graphene.String(required=False)
    refresh_token = graphene.String(required=False)

    @staticmethod
    def mutate(
        root,
        info,
        invitation_code,
        username,
        first_name,
        last_name,
        email,
        telephone=None,
    ):
        invitation = InvitationCode.objects.filter(code=invitation_code).first()
        if invitation:
            if AuthorityUser.objects.filter(username=username).exists():
                raise GraphQLError(f"username {username} already exist")
            authority_user = AuthorityUser.objects.create(
                username=username,
                first_name=first_name,
                last_name=last_name,
                telephone=telephone,
                email=email,
                authority=invitation.authority,
            )

            token = None
            refresh_token = None
            if settings.AUTO_LOGIN_AFTER_REGISTER:
                token = get_token(authority_user)
                refresh_token = create_refresh_token(authority_user)

            return AuthorityUserRegisterMutation(
                me=authority_user, token=token, refresh_token=refresh_token
            )
        else:
            raise GraphQLError(f"invitation code {invitation_code} does not exist")


class Mutation(graphene.ObjectType):
    authority_user_register = AuthorityUserRegisterMutation.Field()
    admin_authority_create = AdminAuthorityCreateMutation.Field()
