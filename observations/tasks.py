from podd_api.celery import app
from observations.models import ObservationImage


@app.task
def generate_observation_image(report_id):
    ObservationImage.objects.get(pk=report_id).generate_thumbnails()
