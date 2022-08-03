import graphene
from graphql_jwt.decorators import login_required

from threads.models import Thread, Comment
from threads.schema.types import CommentType


class Query(graphene.ObjectType):
    comments = graphene.List(CommentType, thread_id=graphene.ID(required=True))

    @staticmethod
    @login_required
    def resolve_comments(root, info, thread_id):
        thread = Thread.objects.get(pk=thread_id)
        return Comment.objects.filter(thread=thread)
