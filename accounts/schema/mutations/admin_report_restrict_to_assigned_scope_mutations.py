import graphene
from graphql_jwt.decorators import login_required, superuser_required

from accounts.report_restrict_to_assigned_scope import (
    set_report_restrict_to_assigned_scope_enabled,
)


class AdminReportRestrictToAssignedScopeUpdateMutation(graphene.Mutation):
    class Arguments:
        enabled = graphene.Boolean(required=True)

    enabled = graphene.Boolean(required=True)

    @staticmethod
    @login_required
    @superuser_required
    def mutate(root, info, enabled):
        set_report_restrict_to_assigned_scope_enabled(enabled)
        return AdminReportRestrictToAssignedScopeUpdateMutation(enabled=enabled)
