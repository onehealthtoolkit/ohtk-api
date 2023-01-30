from cases.models import CaseDefinition, Case, NotificationTemplate
from podd_api.celery import app
from reports.models import IncidentReport
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


@app.task
def evaluate_case_definition(report_id):
    report = IncidentReport.objects.get(pk=report_id)
    if report.test_flag:
        return

    eval_context = report.evaluate_context()
    for definition in CaseDefinition.objects.filter(report_type=report.report_type):
        try:
            if eval_context.eval(definition.condition):
                Case.promote_from_incident_report(report_id)
                return  # do only one promote
        except:
            logger.error(
                f"Error evaluating case definition {definition.condition}",
                exc_info=True,
            )


@app.task
def evaluate_notification_template_after_receive_report(report_id):
    report = IncidentReport.objects.get(pk=report_id)
    if report.test_flag:
        return

    eval_context = report.evaluate_context()
    for template in NotificationTemplate.objects.filter(
        type=NotificationTemplate.Type.REPORT,
        report_type=report.report_type,
    ):
        if template.condition:
            try:
                if eval_context.eval(template.condition):
                    template.send_report_notification(report_id)
            except:
                logger.error(
                    f"Error evaluating notification template condition {template.condition}",
                    exc_info=True,
                )
        else:
            template.send_report_notification(report_id)


@app.task
def evaluate_promote_to_case_notification(case_id):
    case = Case.objects.get(pk=case_id)
    eval_context = case.report.evaluate_context()
    for template in NotificationTemplate.objects.filter(
        type=NotificationTemplate.Type.PROMOTE_TO_CASE,
        report_type=case.report.report_type,
    ):
        if template.condition:
            try:
                if eval_context.eval(template.condition):
                    template.send_report_notification(case.report.id)
            except:
                logger.error(
                    f"Error evaluating promote to case notification condition {template.condition}",
                    exc_info=True,
                )
        else:
            template.send_report_notification(case.report.id)


@app.task
def evaluate_case_transition(case_id, transition_from_step_id, transition_to_step_id):
    case = Case.objects.get(pk=case_id)
    eval_context = case.report.evaluate_context()
    for template in NotificationTemplate.objects.filter(
        type=NotificationTemplate.Type.CASE_TRANSITION,
        report_type=case.report.report_type,
        state_transition__from_step_id=transition_from_step_id,
        state_transition__to_step_id=transition_to_step_id,
    ):
        if template.condition:
            try:
                if eval_context.eval(template.condition):
                    template.send_report_notification(case.report.id)
            except:
                logger.error(
                    f"Error evaluating promote to case notification condition {template.condition}",
                    exc_info=True,
                )
            else:
                template.send_report_notification(case.report.id)
