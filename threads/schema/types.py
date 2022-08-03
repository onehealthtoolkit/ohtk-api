import graphene
from graphene_django import DjangoObjectType

from common.types import AdminValidationProblem
from threads.models import Comment, CommentAttachment


class CommentAttachmentType(DjangoObjectType):
    class Meta:
        model = CommentAttachment


class CommentType(DjangoObjectType):
    thread_id = graphene.Int()
    attachments = graphene.List(CommentAttachmentType)

    class Meta:
        model = Comment
        fields = ["id", "body", "thread_id", "created_by", "attachments"]

    def resolve_attachments(self, info):
        return self.attachments.all()


class CommentCreateSuccess(DjangoObjectType):
    thread_id = graphene.Int()
    attachments = graphene.List(CommentAttachmentType)

    class Meta:
        model = Comment
        fields = ["id", "body", "thread_id", "created_by", "attachments"]

    def resolve_attachments(self, info):
        return self.attachments.all()


class CommentCreateProblem(AdminValidationProblem):
    pass


class CommentCreateResult(graphene.Union):
    class Meta:
        types = (
            CommentCreateSuccess,
            CommentCreateProblem,
        )
