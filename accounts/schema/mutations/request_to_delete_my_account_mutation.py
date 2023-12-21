import graphene
from graphql_jwt.decorators import login_required


class RequestToDeleteMyAccountMutation(graphene.Mutation):
    class Arguments:
        pass

    success = graphene.Boolean()

    @staticmethod
    @login_required
    def mutate(root, info):
        user = info.context.user
        success = True

        return RequestToDeleteMyAccountMutation(success=success)
