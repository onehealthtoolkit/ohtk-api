import graphene
from common.utils import is_duplicate, is_not_empty, check_and_get
from cases.models import NotificationTemplate, StateTransition
from cases.schema.types import (
    AdminNotificationTemplateUpdateProblem,
    AdminNotificationTemplateUpdateResult,
    AdminNotificationTemplateUpdateSuccess,
)
from reports.models.report_type import ReportType


class AdminNotificationTemplateUpdateMutation(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)
        name = graphene.String(required=True)
        state_transition_id = graphene.Int(required=True)
        report_type_id = graphene.UUID(required=True)
        title_template = graphene.String(required=True)
        body_template = graphene.String(required=True)

    result = graphene.Field(AdminNotificationTemplateUpdateResult)

    @staticmethod
    def mutate(
        root,
        info,
        id,
        name,
        state_transition_id,
        report_type_id,
        title_template,
        body_template,
    ):
        try:
            notification_template = NotificationTemplate.objects.get(pk=id)
        except NotificationTemplate.DoesNotExist:
            return AdminNotificationTemplateUpdateMutation(
                result=AdminNotificationTemplateUpdateProblem(
                    fields=[], message="Object not found"
                )
            )

        problems = []
        state_transition, state_transition_problem = check_and_get(
            "state_transition_id", state_transition_id, StateTransition
        )
        if state_transition_problem:
            problems.append(state_transition_problem)

        report_type, report_type_problem = check_and_get(
            "report_type_id", report_type_id, ReportType
        )
        if report_type_problem:
            problems.append(report_type_problem)

        if name_problem := is_not_empty("name", name, "Name must not be empty"):
            problems.append(name_problem)

        if notification_template.name != name:
            if duplicate_problem := is_duplicate("name", name, NotificationTemplate):
                problems.append(duplicate_problem)

        if len(problems) > 0:
            return AdminNotificationTemplateUpdateMutation(
                result=AdminNotificationTemplateUpdateProblem(fields=problems)
            )

        notification_template.name = name
        notification_template.state_transition = state_transition
        notification_template.report_type = report_type
        notification_template.title_template = title_template
        notification_template.body_template = body_template
        notification_template.save()
        return AdminNotificationTemplateUpdateMutation(
            result=AdminNotificationTemplateUpdateSuccess(
                notification_template=notification_template
            )
        )