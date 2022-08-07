import graphene
from easy_thumbnails.files import get_thumbnailer
from graphene_django import DjangoObjectType

from common.types import AdminValidationProblem
from threads.models import Comment, CommentAttachment


class CommentAttachmentType(DjangoObjectType):
    thumbnail = graphene.String()

    class Meta:
        model = CommentAttachment

    def resolve_thumbnail(self, info):
        return get_thumbnailer(self.file)["thumbnail"]


class CommentType(DjangoObjectType):
    thread_id = graphene.Int()
    attachments = graphene.List(CommentAttachmentType)

    class Meta:
        model = Comment
        fields = ["id", "body", "thread_id", "created_by", "attachments", "created_at"]

    def resolve_attachments(self, info):
        return self.attachments.all()


class CommentCreateSuccess(DjangoObjectType):
    thread_id = graphene.Int()
    attachments = graphene.List(CommentAttachmentType)

    class Meta:
        model = Comment
        fields = ["id", "body", "thread_id", "created_by", "attachments", "created_at"]

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
