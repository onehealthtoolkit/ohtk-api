import graphene
from graphene_django import DjangoObjectType

from accounts.models import Authority, AuthorityUser, InvitationCode, Feature, User
from common.types import AdminValidationProblem


class AuthorityType(DjangoObjectType):
    class Meta:
        model = Authority
        fields = (
            "id",
            "code",
            "name",
        )
        filter_fields = {"name": ["istartswith", "exact"]}


class AdminAuthorityQueryType(DjangoObjectType):
    class Meta:
        model = Authority
        fields = (
            "id",
            "code",
            "name",
        )
        filter_fields = {"name": ["istartswith", "exact"]}


class AdminAuthorityUserQueryType(DjangoObjectType):
    class Meta:
        model = AuthorityUser
        fields = ("id", "username", "first_name", "last_name", "email")
        filter_fields = {
            "username": ["istartswith", "exact"],
            "first_name": ["istartswith", "exact"],
            "last_name": ["istartswith", "exact"],
            "email": ["istartswith", "exact"],
        }


class AdminInvitationCodeQueryType(DjangoObjectType):
    class Meta:
        model = InvitationCode
        fields = ("id", "code", "authority", "from_date", "through_date")
        filter_fields = {
            "code": ["istartswith", "exact"],
        }


class InvitationCodeType(DjangoObjectType):
    class Meta:
        model = InvitationCode
        fields = ("id", "authority", "code", "from_date", "through_date")


class UserType(DjangoObjectType):
    class Meta:
        model = User
        fields = ("id", "username", "first_name", "last_name")


class AuthorityUserType(DjangoObjectType):
    class Meta:
        model = AuthorityUser
        fields = ("id", "authority", "username", "first_name", "last_name")


class UserProfileType(graphene.ObjectType):
    id = graphene.Int(required=True)
    username = graphene.String(required=True)
    first_name = graphene.String(required=True)
    last_name = graphene.String(required=True)
    authority_name = graphene.String(required=False)
    authority_id = graphene.Int(required=False)

    def resolve_authority_name(parent, info):
        if hasattr(parent, "authority"):
            return parent.authority.name
        return ""

    def resolve_authority_id(parent, info):
        if hasattr(parent, "authority"):
            return parent.authority.id
        return 0


class CheckInvitationCodeType(DjangoObjectType):
    class Meta:
        model = InvitationCode
        fields = ("code", "authority")


class FeatureType(DjangoObjectType):
    class Meta:
        model = Feature


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


class AdminAuthorityUpdateSuccess(DjangoObjectType):
    class Meta:
        model = Authority


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


class AdminAuthorityUserUpdateSuccess(DjangoObjectType):
    class Meta:
        model = AuthorityUser


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


class AdminInvitationCodeUpdateSuccess(DjangoObjectType):
    class Meta:
        model = InvitationCode


class AdminInvitationCodeUpdateProblem(AdminValidationProblem):
    pass


class AdminInvitationCodeUpdateResult(graphene.Union):
    class Meta:
        types = (
            AdminInvitationCodeUpdateSuccess,
            AdminInvitationCodeUpdateProblem,
        )
