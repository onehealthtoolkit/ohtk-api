import graphene
from django.utils.timezone import now
from graphql import GraphQLError
from graphql_jwt.decorators import login_required

from accounts.models import InvitationCode
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
