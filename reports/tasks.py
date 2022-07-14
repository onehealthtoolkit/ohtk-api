from podd_api.celery import app
from reports.models import IncidentReport, ReporterNotification


@app.task
def evaluate_reporter_notification(report_id):
    report = IncidentReport.objects.get(pk=report_id)
    eval_context = report.evaluate_context()
    for definition in ReporterNotification.objects.filter(
        report_type=report.report_type
    ):
        try:
            if eval_context.eval(definition.condition):
                definition.send_message(eval_context)
                return
        except:
            pass
