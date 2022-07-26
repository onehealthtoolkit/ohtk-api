import graphene
from common.utils import is_not_empty, check_and_get
from cases.models import AuthorityNotification, NotificationTemplate
from cases.schema.types import (
    AdminAuthorityNotificationUpsertProblem,
    AdminAuthorityNotificationUpsertResult,
)


class AdminAuthorityNotificationUpsertMutation(graphene.Mutation):
    class Arguments:
        notification_template_id = graphene.Int(required=True)
        to = graphene.String(required=True)

    result = graphene.Field(AdminAuthorityNotificationUpsertResult)

    @staticmethod
    def mutate(root, info, notification_template_id, to):
        user = info.context.user
        print(user)
        problems = []
        notification_template, problem = check_and_get(
            "notification_template_id", notification_template_id, NotificationTemplate
        )
        if problem:
            problems.append(problem)

        if to_problem := is_not_empty("to", to, "To must not be empty"):
            problems.append(to_problem)

        if len(problems) > 0:
            return AdminAuthorityNotificationUpsertMutation(
                result=AdminAuthorityNotificationUpsertProblem(fields=problems)
            )

        try:
            authority_notification = AuthorityNotification.objects.get(
                template=notification_template
            )
            authority_notification.authority = user.authorityuser.authority
            authority_notification.template = notification_template
            authority_notification.to = to
            authority_notification.save()
        except AuthorityNotification.DoesNotExist:
            authority_notification = AuthorityNotification(
                authority=user.authorityuser.authority,
                template=notification_template,
                to=to,
            )
            authority_notification.save()
        return AdminAuthorityNotificationUpsertMutation(result=authority_notification)
