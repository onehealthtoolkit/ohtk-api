import graphene
from graphql_jwt.decorators import login_required

from threads.models import Comment
from threads.schema.types import CommentUpdateResult


class CommentUpdateMutation(graphene.Mutation):
    class Arguments:
        comment_id = graphene.Int(required=True)
        body = graphene.String(required=True)

    result = graphene.Field(CommentUpdateResult)

    @staticmethod
    @login_required
    def mutate(root, info, comment_id, body):
        user = info.context.user
        try:
            comment = Comment.objects.get(pk=comment_id, created_by=user)
        except Comment.DoesNotExist:
            raise PermissionError()
        comment.body = body
        comment.save(update_fields=("body",))

        return {"result": comment}
