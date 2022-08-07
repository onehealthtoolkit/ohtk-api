import graphene
from graphene_file_upload.scalars import Upload
from graphql_jwt.decorators import login_required

from common.utils import is_not_empty
from threads.models import Thread, Comment, CommentAttachment
from threads.schema.types import CommentCreateResult, CommentCreateProblem


class CommentCreateMutation(graphene.Mutation):
    class Arguments:
        thread_id = graphene.Int(required=True)
        body = graphene.String(required=True)
        files = graphene.List(Upload)

    result = graphene.Field(CommentCreateResult)

    @staticmethod
    @login_required
    def mutate(root, info, thread_id, body, files=None):
        user = info.context.user

        thread = Thread.objects.get(pk=thread_id)
        problems = []
        if body_problem := is_not_empty("body", body, "Body must not be empty"):
            problems.append(body_problem)

        if len(problems) > 0:
            return CommentCreateMutation(result=CommentCreateProblem(fields=problems))

        comment = Comment.objects.create(
            body=body,
            thread=thread,
            created_by=user,
        )
        if files:
            for file in files:
                attachment = CommentAttachment.objects.create(
                    comment=comment,
                    file=file,
                )

        return {"result": comment}
