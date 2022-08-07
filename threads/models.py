from django.db import models
from easy_thumbnails.fields import ThumbnailerField

from accounts.models import BaseModel, User, BaseModelManager


class Thread(BaseModel):
    objects = BaseModelManager()

    def delete(self, hard=False, **kwargs):
        for comment in self.comments.all():
            comment.delete(hard)
        super().delete(hard, **kwargs)


class Comment(BaseModel):
    objects = BaseModelManager()

    thread = models.ForeignKey(
        Thread, related_name="comments", on_delete=models.CASCADE
    )
    body = models.TextField()
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)

    def delete(self, hard=False, **kwargs):
        for attachment in self.attachments.all():
            attachment.delete(hard)
        super().delete(hard, **kwargs)


class CommentAttachment(BaseModel):
    objects = BaseModelManager()

    comment = models.ForeignKey(
        Comment, on_delete=models.CASCADE, related_name="attachments"
    )
    file = ThumbnailerField(upload_to="attachments")
