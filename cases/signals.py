import django
from django.dispatch import receiver

from cases import tasks
from cases.models import Case
from reports.models import IncidentReport
from reports.signals import incident_report_submitted

case_promoted = django.dispatch.Signal()
case_state_forwarded = django.dispatch.Signal()


@receiver(
    incident_report_submitted,
    sender=IncidentReport,
    dispatch_uid="evaluate_notification_template_after_receive_report",
)
def evaluate_notification_template_after_receive_report(sender, report, **kwargs):
    tasks.evaluate_notification_template_after_receive_report.delay(report.id)


@receiver(
    incident_report_submitted,
    sender=IncidentReport,
    dispatch_uid="evaluate_case_definition_after_receive_report",
)
def evaluate_case_definition_after_receive_report(sender, report, **kwargs):
    tasks.evaluate_case_definition.delay(report.id)


@receiver(
    case_promoted,
    sender=Case,
    dispatch_uid="promote_to_case_notification",
)
def promote_to_case_notification(sender, case, **kwargs):
    tasks.evaluate_promote_to_case_notification.delay(case.id)


@receiver(
    case_state_forwarded,
    sender=Case,
    dispatch_uid="evaluate_case_state_forwarded_notification",
)
def transition_notification(sender, case, from_step_id, to_step_id, **kwargs):
    tasks.evaluate_case_transition.delay(case.id, from_step_id, to_step_id)
