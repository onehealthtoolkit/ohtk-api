import graphene
from graphql_jwt.decorators import login_required


class RequestToDeleteMyAccountMutation(graphene.Mutation):
    class Arguments:
        pass

    success = graphene.Boolean()

    @staticmethod
    def mutate(root, info):
        user = info.context.user

        if not user.is_authenticated:
            return RequestToDeleteMyAccountMutation(success=False)

        user.is_active = False
        user.first_name = ""
        user.last_name = ""
        user.email = ""
        user.save()

        if user.is_authority_user:
            user.authorityuser.avatar_url = None
            user.authorityuser.thumbnail_avatar_url = None
            user.authorityuser.telephone = None
            user.authorityuser.save()

        success = True

        return RequestToDeleteMyAccountMutation(success=success)
