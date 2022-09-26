from podd_api.celery import app
from reports.models import IncidentReport, ReporterNotification, Image


@app.task
def evaluate_reporter_notification(report_id):
    report = IncidentReport.objects.get(pk=report_id)
    eval_context = report.evaluate_context()
    for definition in ReporterNotification.objects.filter(
        report_type=report.report_type
    ):
        try:
            should_send_msg = eval_context.eval(definition.condition)
        except:
            should_send_msg = False
        if should_send_msg:
            definition.send_message(report.template_context(), report.reported_by)
            return


@app.task
def generate_report_image(report_id):
    Image.objects.get(pk=report_id).generate_thumbnails()
