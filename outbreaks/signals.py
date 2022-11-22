from django.dispatch import receiver
from cases.models import Case
from cases.signals import case_state_forwarded
from .tasks import evaluate_outbreak_plan


@receiver(
    case_state_forwarded,
    sender=Case,
    dispatch_uid="evaluate_outbreak_plan",
)
def transition_notification(sender, case, to_step_id, **kwargs):
    evaluate_outbreak_plan.delay(case.id, to_step_id)
