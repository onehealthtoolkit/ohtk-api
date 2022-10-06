import graphene
from graphql_jwt.decorators import user_passes_test, login_required

from accounts.utils import is_superuser
from common.utils import is_not_empty, check_and_get
from reports.models import ReporterNotification, ReportType
from reports.schema.types import (
    AdminReporterNotificationCreateProblem,
    AdminReporterNotificationCreateResult,
)


class AdminReporterNotificationCreateMutation(graphene.Mutation):
    class Arguments:
        report_type_id = graphene.UUID(required=True)
        description = graphene.String(required=True)
        condition = graphene.String(required=True)
        title_template = graphene.String(required=True)
        template = graphene.String(required=True)
        is_active = graphene.Boolean(required=None, default_value=True)

    result = graphene.Field(AdminReporterNotificationCreateResult)

    @staticmethod
    @login_required
    @user_passes_test(is_superuser)
    def mutate(
        root,
        info,
        report_type_id,
        description,
        condition,
        title_template,
        template,
        is_active,
    ):
        problems = []

        report_type, problem = check_and_get(
            "report_type_id", report_type_id, ReportType
        )
        if problem:
            problems.append(problem)

        if description_problem := is_not_empty(
            "description", description, "Description must not be empty"
        ):
            problems.append(description_problem)

        if condition_problem := is_not_empty(
            "condition", condition, "Condition must not be empty"
        ):
            problems.append(condition_problem)

        if title_template_problem := is_not_empty(
            "titleTemplate", title_template, "Title template must not be empty"
        ):
            problems.append(title_template_problem)

        if template_problem := is_not_empty(
            "template", template, "Template must not be empty"
        ):
            problems.append(template_problem)

        if len(problems) > 0:
            return AdminReporterNotificationCreateMutation(
                result=AdminReporterNotificationCreateProblem(fields=problems)
            )

        reporter_notification = ReporterNotification.objects.create(
            report_type=report_type,
            description=description,
            condition=condition,
            title_template=title_template,
            template=template,
            is_active=is_active,
        )
        return AdminReporterNotificationCreateMutation(result=reporter_notification)
