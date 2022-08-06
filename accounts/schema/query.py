import graphene
from django.utils.timezone import now
from graphql import GraphQLError
from graphql_jwt.decorators import login_required

from accounts.models import AuthorityUser, InvitationCode, Feature, Authority
from accounts.schema.types import (
    AdminInvitationCodeQueryType,
    AuthorityUserType,
    InvitationCodeType,
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
    admin_authority_get = graphene.Field(
        AdminAuthorityQueryType, id=graphene.ID(required=True)
    )
    admin_authority_query = DjangoPaginationConnectionField(AdminAuthorityQueryType)
    admin_authority_inherit_lookup = DjangoPaginationConnectionField(AuthorityType)
    admin_authority_user_query = DjangoPaginationConnectionField(
        AdminAuthorityUserQueryType
    )
    admin_invitation_code_query = DjangoPaginationConnectionField(
        AdminInvitationCodeQueryType
    )
    invitation_code = graphene.Field(InvitationCodeType, id=graphene.ID(required=True))
    authority_user = graphene.Field(AuthorityUserType, id=graphene.ID(required=True))

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
            return invitation
        raise GraphQLError(f"code {code} not found!")

    @staticmethod
    def resolve_features(root, info):
        return Feature.objects.all()

    @staticmethod
    @login_required
    def resolve_authorities(root, info, **kwargs):
        user = info.context.user
        if not user.is_superuser:
            raise GraphQLError("Permission denied.")
        return Authority.objects.all()

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
        if not user.is_superuser:
            raise GraphQLError("Permission denied.")
        return AuthorityUser.objects.get(id=id)

    @staticmethod
    @login_required
    def resolve_invitation_code(root, info, id):
        user = info.context.user
        if not user.is_superuser:
            raise GraphQLError("Permission denied.")
        return InvitationCode.objects.get(id=id)
