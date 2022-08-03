from django.db import models

from accounts.models import BaseModel, User


class Thread(BaseModel):
    pass


class Comment(BaseModel):
    thread = models.ForeignKey(
        Thread, related_name="comments", on_delete=models.CASCADE
    )
    body = models.TextField()
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)


class CommentAttachment(BaseModel):
    comment = models.ForeignKey(
        Comment, on_delete=models.CASCADE, related_name="attachments"
    )
    file = models.FileField(upload_to="attachments")
