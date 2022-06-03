import graphene
from django.utils.timezone import now
from graphql import GraphQLError
from graphql_jwt.decorators import login_required

from accounts.models import InvitationCode, Feature, Authority
from accounts.schema.types import (
    UserProfileType,
    FeatureType,
    AuthorityType,
    AdminAuthorityQueryType,
    AdminAuthorityUserQueryType,
)
from accounts.schema.types import CheckInvitationCodeType
from pagination import DjangoPaginationConnectionField


class Query(graphene.ObjectType):
    me = graphene.Field(UserProfileType)
    check_invitation_code = graphene.Field(
        CheckInvitationCodeType, code=graphene.String(required=True)
    )
    features = graphene.List(FeatureType)
    authorities = DjangoPaginationConnectionField(AuthorityType)
    authority = graphene.Field(AuthorityType, id=graphene.ID(required=True))
    adminAuthorityQuery = DjangoPaginationConnectionField(AdminAuthorityQueryType)
    adminAuthorityUserQuery = DjangoPaginationConnectionField(
        AdminAuthorityUserQueryType
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

    @staticmethod
    def resolve_features(root, info):
        return Feature.objects.all()

    @staticmethod
    def resolve_authorities(root, info, **kwargs):
        user = info.context.user
        if not user.is_superuser:
            raise GraphQLError("Permission denied.")
        return Authority.objects.all()

    @staticmethod
    def resolve_authority(root, info, id):
        user = info.context.user
        if not user.is_superuser:
            raise GraphQLError("Permission denied.")
        return Authority.objects.get(id=id)
