import graphene
from common.utils import is_not_empty
from reports.models import ReporterNotification
from reports.schema.types import (
    AdminReporterNotificationUpdateProblem,
    AdminReporterNotificationUpdateResult,
    AdminReporterNotificationUpdateSuccess,
)


class AdminReporterNotificationUpdateMutation(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)
        description = graphene.String(required=True)
        condition = graphene.String(required=True)
        template = graphene.String(required=True)
        is_active = graphene.Boolean(required=None, default_value=True)

    result = graphene.Field(AdminReporterNotificationUpdateResult)

    @staticmethod
    def mutate(root, info, id, description, condition, template, is_active):
        try:
            reporter_notification = ReporterNotification.objects.get(pk=id)
        except ReporterNotification.DoesNotExist:
            return AdminReporterNotificationUpdateMutation(
                result=AdminReporterNotificationUpdateProblem(
                    fields=[], message="Object not found"
                )
            )

        problems = []
        if description_problem := is_not_empty(
            "description", description, "Description must not be empty"
        ):
            problems.append(description_problem)

        if condition_problem := is_not_empty(
            "condition", condition, "Condition must not be empty"
        ):
            problems.append(condition_problem)

        if len(problems) > 0:
            return AdminReporterNotificationUpdateMutation(
                result=AdminReporterNotificationUpdateProblem(fields=problems)
            )

        reporter_notification.description = description
        reporter_notification.condition = condition
        reporter_notification.template = template
        reporter_notification.is_active = is_active
        reporter_notification.save()
        return AdminReporterNotificationUpdateMutation(
            result=AdminReporterNotificationUpdateSuccess(
                reporter_notification=reporter_notification
            )
        )
