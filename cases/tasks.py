from cases.models import CaseDefinition, Case, NotificationTemplate
from podd_api.celery import app
from reports.models import IncidentReport


@app.task
def evaluate_case_definition(report_id):
    report = IncidentReport.objects.get(pk=report_id)
    eval_context = report.evaluate_context()
    for definition in CaseDefinition.objects.filter(report_type=report.report_type):
        try:
            if eval_context.eval(definition.condition):
                Case.promote_from_incident_report(report_id)
                return  # do only one promote
        except:
            pass


@app.task
def evaluate_notification_template_after_receive_report(report_id):
    report = IncidentReport.objects.get(pk=report_id)
    eval_context = report.evaluate_context()
    for template in NotificationTemplate.objects.filter(
        type=NotificationTemplate.Type.REPORT
    ):
        if template.condition:
            try:
                if eval_context.eval(template.condition):
                    template.send_report_notification(report_id)
            except:
                pass
        else:
            template.send_report_notification(report_id)


@app.task
def evaluate_promote_to_case_notification(case_id):
    case = Case.objects.get(pk=case_id)
    eval_context = case.report.evaluate_context()
    for template in NotificationTemplate.objects.filter(
        type=NotificationTemplate.Type.PROMOTE_TO_CASE
    ):
        if template.condition:
            try:
                if eval_context.eval(template.condition):
                    template.send_report_notification(case.report.id)
            except:
                pass
        else:
            template.send_case_notification(case_id)
