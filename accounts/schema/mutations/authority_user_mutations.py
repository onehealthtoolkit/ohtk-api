import graphene
from django.conf import settings
from graphql import GraphQLError
from graphql_jwt.refresh_token.shortcuts import create_refresh_token
from graphql_jwt.shortcuts import get_token

from accounts.models import InvitationCode, AuthorityUser
from accounts.schema.types import UserProfileType


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
