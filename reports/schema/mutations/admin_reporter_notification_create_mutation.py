import graphene
from common.utils import is_not_empty
from reports.models import ReporterNotification
from reports.schema.types import (
    AdminReporterNotificationCreateProblem,
    AdminReporterNotificationCreateResult,
)


class AdminReporterNotificationCreateMutation(graphene.Mutation):
    class Arguments:
        description = graphene.String(required=True)
        condition = graphene.String(required=True)
        template = graphene.String(required=True)
        is_active = graphene.Boolean(required=None, default_value=True)

    result = graphene.Field(AdminReporterNotificationCreateResult)

    @staticmethod
    def mutate(root, info, description, condition, template, is_active):
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
            return AdminReporterNotificationCreateMutation(
                result=AdminReporterNotificationCreateProblem(fields=problems)
            )

        reporter_notification = ReporterNotification.objects.create(
            description=description,
            condition=condition,
            template=template,
            is_active=is_active,
        )
        return AdminReporterNotificationCreateMutation(result=reporter_notification)
