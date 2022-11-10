import graphene
from graphql_jwt.decorators import login_required, superuser_required, user_passes_test

from accounts.utils import is_officer_role, is_superuser, fn_or, is_admin_role
from cases.models import AuthorityNotification


class AdminAuthorityNotificationDeleteMutation(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)

    success = graphene.Boolean()

    @staticmethod
    @login_required
    @user_passes_test(fn_or(is_superuser, is_officer_role, is_admin_role))
    def mutate(root, info, id):
        definition = AuthorityNotification.objects.get(pk=id)
        definition.delete(hard=True)
        return {"success": True}
