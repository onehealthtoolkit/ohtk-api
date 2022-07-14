import graphene
from graphql_jwt.decorators import login_required

from accounts.models import User


class RegisterFcmTokenMutation(graphene.Mutation):
    class Arguments:
        user_id = graphene.String(required=True)
        token = graphene.String(required=True)

    success = graphene.Boolean()

    @staticmethod
    @login_required
    def mutate(root, info, user_id, token):
        user = User.objects.get(pk=user_id)
        if user.fcm_token != token:
            user.fcm_token = token
            user.save(update_fields=("fcm_token",))
        return {"success": True}
