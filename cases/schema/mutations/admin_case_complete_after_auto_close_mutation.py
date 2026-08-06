import graphene
from django.core.exceptions import ValidationError
from graphene.types.generic import GenericScalar
from graphql import GraphQLError
from graphql_jwt.decorators import login_required

from cases.models import Case
from cases.schema.mutations.admin_case_close_mutation import _assert_can_manage_case
from cases.schema.types import CaseType
from cases.services.case_close import complete_system_closed_case


class AdminCaseCompleteAfterAutoCloseMutation(graphene.Mutation):
    """
    CO3b: fill Layer2 close data on a system-timeout-finished case.
    Does not reopen; keeps close_source=system and stopped_at.
    """

    class Arguments:
        case_id = graphene.UUID(required=True)
        payload = GenericScalar(required=False)

    result = graphene.Field(CaseType)

    @staticmethod
    @login_required
    def mutate(root, info, case_id, payload=None):
        try:
            case = Case.objects.select_related("report", "report__report_type").get(
                pk=case_id
            )
        except Case.DoesNotExist:
            raise GraphQLError("Case not found")

        user = info.context.user
        _assert_can_manage_case(user, case)

        if payload is None:
            merged = {}
        elif isinstance(payload, dict):
            merged = dict(payload)
        else:
            raise GraphQLError("payload must be an object")

        try:
            complete_system_closed_case(case, actor=user, payload=merged)
        except ValidationError as exc:
            msg = "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc)
            raise GraphQLError(msg)

        case.refresh_from_db()
        return AdminCaseCompleteAfterAutoCloseMutation(result=case)
