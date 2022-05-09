import graphene
from graphene_django import DjangoObjectType

from accounts.models import Authority, InvitationCode, Feature


class AuthorityType(DjangoObjectType):
    class Meta:
        model = Authority
        fields = (
            "id",
            "code",
            "name",
        )
        filter_fields = {"name": ["istartswith", "exact"]}


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
