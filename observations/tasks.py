from podd_api.celery import app
from observations.models import RecordImage


@app.task
def generate_record_image(image_id):
    RecordImage.objects.get(pk=image_id).generate_thumbnails()
