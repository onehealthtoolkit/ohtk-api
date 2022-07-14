from cases.models import CaseDefinition, Case
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
