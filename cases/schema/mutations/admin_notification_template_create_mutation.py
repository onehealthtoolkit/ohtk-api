import graphene
from common.utils import is_duplicate, is_not_empty, check_and_get
from cases.models import NotificationTemplate, StateTransition
from cases.schema.types import (
    AdminNotificationTemplateCreateProblem,
    AdminNotificationTemplateCreateResult,
)

from reports.models.report_type import ReportType


class AdminNotificationTemplateCreateMutation(graphene.Mutation):
    class Arguments:
        name = graphene.String(required=True)
        type = graphene.String(required=True)
        state_transition_id = graphene.Int(required=None)
        report_type_id = graphene.UUID(required=True)
        title_template = graphene.String(required=True)
        body_template = graphene.String(required=True)

    result = graphene.Field(AdminNotificationTemplateCreateResult)

    @staticmethod
    def mutate(
        root,
        info,
        name,
        type,
        state_transition_id,
        report_type_id,
        title_template,
        body_template,
    ):
        problems = []
        state_transition = None
        if state_transition_id:
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

        if duplicate_problem := is_duplicate("name", name, NotificationTemplate):
            problems.append(duplicate_problem)

        if len(problems) > 0:
            return AdminNotificationTemplateCreateMutation(
                result=AdminNotificationTemplateCreateProblem(fields=problems)
            )

        notification_template = NotificationTemplate.objects.create(
            name=name,
            type=type,
            state_transition=state_transition,
            report_type=report_type,
            title_template=title_template,
            body_template=body_template,
        )
        return AdminNotificationTemplateCreateMutation(result=notification_template)
