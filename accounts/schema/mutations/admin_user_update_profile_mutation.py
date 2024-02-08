import graphene
from graphql_jwt.decorators import login_required

from accounts.models import AuthorityUser


class AdminUserUpdateProfileMutation(graphene.Mutation):
    class Arguments:
        first_name = graphene.String(required=True)
        last_name = graphene.String(required=True)
        telephone = graphene.String(required=False)
        address = graphene.String(required=False)

    success = graphene.Boolean()

    @staticmethod
    @login_required
    def mutate(root, info, first_name, last_name, telephone, address):
        user = info.context.user
        if user.is_authority_user:
            update_user = user.authorityuser
        else:
            update_user = user

        update_user.first_name = first_name
        update_user.last_name = last_name
        update_user.telephone = telephone
        update_user.address = address
        update_user.save()
        return AdminUserUpdateProfileMutation(success=True)
