import graphene
from django.core.exceptions import ValidationError
from graphene.types.generic import GenericScalar
from graphql import GraphQLError
from graphql_jwt.decorators import login_required

from accounts.models import AuthorityUser
from cases.models import Case
from cases.schema.types import CaseType
from cases.services.case_close import close_case


def _assert_can_manage_case(user, case):
    if user.is_superuser:
        return
    if not getattr(user, "is_authority_user", False):
        raise GraphQLError("Not authorized to close this case")
    if user.is_authority_role_in([AuthorityUser.Role.REPORTER]):
        raise GraphQLError("Not authorized to close this case")
    authority = user.authorityuser.authority
    in_charge = case.authorities.filter(pk__in=authority.all_inherits_down()).exists()
    if not in_charge and case.report_id:
        in_charge = case.report.relevant_authorities.filter(
            pk__in=authority.all_inherits_down()
        ).exists()
    if not in_charge:
        raise GraphQLError("User's authority is not in charge of this case")


class AdminCaseCloseMutation(graphene.Mutation):
    """Officer close: Layer1 completion + Layer2 payload (validated)."""

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

        # Merge open-case draft payload with provided payload.
        base = dict(case.close_payload) if isinstance(case.close_payload, dict) else {}
        if payload is None:
            merged = base
        elif isinstance(payload, dict):
            merged = {**base, **payload}
        else:
            raise GraphQLError("payload must be an object")

        try:
            close_case(
                case,
                source=Case.CloseSource.OFFICER,
                actor=user,
                payload=merged,
            )
        except ValidationError as exc:
            msg = "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc)
            raise GraphQLError(msg)

        case.refresh_from_db()
        return AdminCaseCloseMutation(result=case)
