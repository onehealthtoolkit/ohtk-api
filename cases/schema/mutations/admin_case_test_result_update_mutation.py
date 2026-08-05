import graphene
from django.core.exceptions import ValidationError
from graphql import GraphQLError
from graphql_jwt.decorators import login_required

from accounts.models import AuthorityUser
from cases.models import Case
from cases.schema.types import CaseType
from cases.services.case_close import update_open_case_close_payload


class AdminCaseTestResultUpdateMutation(graphene.Mutation):
    """
    Write Layer2 test_result key while case is open.
    Never writes report.ai_suspected. Closed cases rejected.
    """

    class Arguments:
        case_id = graphene.UUID(required=True)
        test_result = graphene.String(required=True)

    result = graphene.Field(CaseType)

    @staticmethod
    @login_required
    def mutate(root, info, case_id, test_result):
        try:
            case = Case.objects.select_related("report").get(pk=case_id)
        except Case.DoesNotExist:
            raise GraphQLError("Case not found")

        user = info.context.user
        if not user.is_superuser:
            if not getattr(user, "is_authority_user", False):
                raise GraphQLError("Not authorized to update case test result")
            if user.is_authority_role_in([AuthorityUser.Role.REPORTER]):
                raise GraphQLError("Not authorized to update case test result")
            authority = user.authorityuser.authority
            in_charge = case.authorities.filter(
                pk__in=authority.all_inherits_down()
            ).exists()
            if not in_charge and case.report_id:
                in_charge = case.report.relevant_authorities.filter(
                    pk__in=authority.all_inherits_down()
                ).exists()
            if not in_charge:
                raise GraphQLError("User's authority is not in charge of this case")

        try:
            update_open_case_close_payload(
                case, {"test_result": test_result if test_result is not None else ""}
            )
        except ValidationError as exc:
            msg = "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc)
            raise GraphQLError(msg)

        case.refresh_from_db()
        return AdminCaseTestResultUpdateMutation(result=case)
