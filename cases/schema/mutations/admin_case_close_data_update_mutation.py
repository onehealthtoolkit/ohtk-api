import graphene
from django.core.exceptions import ValidationError
from graphene.types.generic import GenericScalar
from graphql import GraphQLError
from graphql_jwt.decorators import login_required

from cases.models import Case
from cases.schema.types import CaseType
from cases.services.case_close import update_finished_case_close_data


class AdminCaseCloseDataUpdateMutation(graphene.Mutation):
    """
    Superuser-only: edit Layer2 close data on a finished case (no reopen).
    """

    class Arguments:
        case_id = graphene.UUID(required=True)
        payload = GenericScalar(required=False)

    result = graphene.Field(CaseType)

    @staticmethod
    @login_required
    def mutate(root, info, case_id, payload=None):
        user = info.context.user
        if not getattr(user, "is_superuser", False):
            raise GraphQLError("Only superuser can edit finished close data")

        try:
            case = Case.objects.select_related("report", "report__report_type").get(
                pk=case_id
            )
        except Case.DoesNotExist:
            raise GraphQLError("Case not found")

        if payload is None:
            merged = {}
        elif isinstance(payload, dict):
            merged = dict(payload)
        else:
            raise GraphQLError("payload must be an object")

        try:
            update_finished_case_close_data(case, actor=user, payload=merged)
        except ValidationError as exc:
            msg = "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc)
            raise GraphQLError(msg)

        case.refresh_from_db()
        return AdminCaseCloseDataUpdateMutation(result=case)
