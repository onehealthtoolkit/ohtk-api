import graphene
from graphql import GraphQLError
from graphql_jwt.decorators import login_required, superuser_required, user_passes_test

from accounts.utils import is_officer_role, is_superuser, fn_or, is_admin_role
from cases.models import AuthorityNotification


class AdminAuthorityNotificationDeleteMutation(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)

    success = graphene.Boolean()

    @staticmethod
    @login_required
    def mutate(root, info, id):
        user = info.context.user

        definition = AuthorityNotification.objects.get(pk=id)
        if user.is_superuser:
            pass
        elif user.is_authority_user:
            if user.authority_role == "ADM" or user.authority_role == "OFF":
                if definition.authority_id != user.authorityuser.authority_id:
                    raise GraphQLError("Permission denied")
        else:
            raise GraphQLError("Permission denied")

        definition.delete(hard=True)
        return {"success": True}
