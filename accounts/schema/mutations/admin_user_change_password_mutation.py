import graphene
from graphql_jwt.decorators import login_required


class AdminUserChangePasswordMutation(graphene.Mutation):
    class Arguments:
        new_password = graphene.String(required=True)

    success = graphene.Boolean()

    @staticmethod
    @login_required
    def mutate(root, info, new_password):
        user = info.context.user
        user.set_password(new_password)
        user.save(update_fields=("password",))
        return {"success": True}
