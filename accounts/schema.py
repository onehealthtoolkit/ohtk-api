import graphene
from django.utils.timezone import now
from graphql import GraphQLError
from graphql_jwt.decorators import login_required

from accounts.models import InvitationCode, AuthorityUser
from accounts.types import UserProfileType, CheckInvitationCodeType


class Query(graphene.ObjectType):
    me = graphene.Field(UserProfileType)
    check_invitation_code = graphene.Field(
        CheckInvitationCodeType, code=graphene.String(required=True)
    )

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


class AuthorityUserRegisterMutation(graphene.Mutation):
    class Arguments:
        invitation_code = graphene.String(required=True)
        username = graphene.String(required=True)
        first_name = graphene.String(required=True)
        last_name = graphene.String(required=True)
        telephone = graphene.String(required=False)
        email = graphene.String(required=True)

    me = graphene.Field(UserProfileType)

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
            return AuthorityUserRegisterMutation(me=authority_user)
        else:
            raise GraphQLError(f"invitation code {invitation_code} does not exist")


class Mutation(graphene.ObjectType):
    authority_user_register = AuthorityUserRegisterMutation.Field()
