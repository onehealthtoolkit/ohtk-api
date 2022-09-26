from podd_api.celery import app
from threads.models import CommentAttachment


@app.task
def generate_comment_attachment(comment_id):
    CommentAttachment.objects.get(pk=comment_id).generate_thumbnails()
