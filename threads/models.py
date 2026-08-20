from django.db import models
from easy_thumbnails.fields import ThumbnailerField

from accounts.models import User
from common.models import BaseModel, BaseModelManager
from threads.attachment_files import is_image_attachment


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

    def generate_thumbnails(self):
        if not self.file or not is_image_attachment(self.file.name):
            return
        try:
            self.file.generate_all_thumbnails()
        except Exception:
            return
