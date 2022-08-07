import graphene
from graphql_jwt.decorators import login_required, superuser_required

from threads.models import Comment


class CommentDeleteMutation(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)

    success = graphene.Boolean()

    @staticmethod
    @login_required
    @superuser_required
    def mutate(root, info, id):
        definition = Comment.objects.get(pk=id)
        definition.delete()
        return {"success": True}
