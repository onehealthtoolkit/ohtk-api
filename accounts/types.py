import graphene
from graphene_django import DjangoObjectType

from accounts.models import Authority, InvitationCode, Feature, User


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


class UserType(DjangoObjectType):
    class Meta:
        model = User
        fields = ("id", "username", "first_name", "last_name")


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


class AdminFieldValidationProblem(graphene.ObjectType):
    name = graphene.String(required=True)
    message = graphene.String(required=True)


class AdminValidationProblem(graphene.ObjectType):
    fields = graphene.List(AdminFieldValidationProblem, required=False)
    message = graphene.String(required=False)


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
