import graphene
from graphql_jwt.decorators import login_required, user_passes_test

from accounts.utils import is_superuser
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
        type = graphene.String(required=True)
        condition = graphene.String(required=None)
        state_transition_id = graphene.Int(required=None)
        report_type_id = graphene.UUID(required=True)
        title_template = graphene.String(required=True)
        body_template = graphene.String(required=True)

    result = graphene.Field(AdminNotificationTemplateUpdateResult)

    @staticmethod
    @login_required
    @user_passes_test(is_superuser)
    def mutate(
        root,
        info,
        id,
        name,
        type,
        condition,
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

        if notification_template.name != name:
            if duplicate_problem := is_duplicate("name", name, NotificationTemplate):
                problems.append(duplicate_problem)

        if len(problems) > 0:
            return AdminNotificationTemplateUpdateMutation(
                result=AdminNotificationTemplateUpdateProblem(fields=problems)
            )

        notification_template.name = name
        notification_template.type = type
        notification_template.condition = condition
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
