import graphene
from graphene_django import DjangoObjectType

from accounts.models import Authority, AuthorityUser, InvitationCode, Feature, User
from common.types import AdminValidationProblem


class AuthorityInheritType(DjangoObjectType):
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
        )
        filter_fields = {"name": ["istartswith", "exact"]}

    inherits = graphene.List(AuthorityInheritType, required=True)

    def resolve_inherits(self, info, **kwargs):
        results = []
        for authority in self.inherits.all():
            results.append(authority)
        return results


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
    telephone = graphene.String()

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
        if self.is_authority_user():
            return self.authorityuser.telephone
        else:
            return ""


class AuthorityUserType(DjangoObjectType):
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
        )


class UserProfileType(graphene.ObjectType):
    id = graphene.Int(required=True)
    username = graphene.String(required=True)
    first_name = graphene.String(required=True)
    last_name = graphene.String(required=True)
    authority_name = graphene.String(required=False)
    authority_id = graphene.Int(required=False)

    def resolve_authority_name(self, info):
        if self.is_authority_user():
            return self.authority.name
        return ""

    def resolve_authority_id(self, info):
        if hasattr(self, "authority"):
            return self.authority.id
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
