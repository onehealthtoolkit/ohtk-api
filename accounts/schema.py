import graphene
from graphql_jwt.decorators import login_required


class UserProfileType(graphene.ObjectType):
    id = graphene.Int(required=True)
    username = graphene.String(required=True)
    first_name = graphene.String(required=True)
    last_name = graphene.String(required=True)
    authority_name = graphene.String(required=False)

    def resolve_authority_name(parent, info):
        if hasattr(parent, "authority"):
            return parent.authority.name
        return ""


class Query(graphene.ObjectType):
    me = graphene.Field(UserProfileType)

    @staticmethod
    @login_required
    def resolve_me(root, info):
        user = info.context.user
        if hasattr(user, "authorityuser"):
            return user.authorityuser
        return user
