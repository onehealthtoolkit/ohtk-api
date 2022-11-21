import graphene
from graphql_jwt.decorators import login_required


class ConfirmConsentMutation(graphene.Mutation):
    class Arguments:
        pass

    ok = graphene.Boolean()

    @staticmethod
    @login_required
    def mutate(root, info):
        user = info.context.user
        ok = False
        if user.is_authority_user:
            user.authorityuser.consent = True
            user.authorityuser.save(update_fields=["consent"])
            ok = True
        return ConfirmConsentMutation(ok=ok)
