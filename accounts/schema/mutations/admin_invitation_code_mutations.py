import graphene
from graphql_jwt.decorators import login_required, user_passes_test, superuser_required

from accounts.models import Authority, InvitationCode, AuthorityUser

from accounts.schema.types import (
    AdminInvitationCodeCreateResult,
    AdminInvitationCodeUpdateResult,
    AdminInvitationCodeUpdateProblem,
    AdminInvitationCodeCreateProblem,
    AdminInvitationCodeUpdateSuccess,
)
from accounts.utils import (
    fn_or,
    is_superuser,
    is_officer_role,
    check_permission_on_inherits_down,
    check_permission_authority_must_be_the_same,
)
from common.utils import is_duplicate, is_not_empty
from common.types import AdminFieldValidationProblem


class AdminInvitationCodeCreateMutation(graphene.Mutation):
    class Arguments:
        code = graphene.String(required=True)
        authority_id = graphene.Int(required=True)
        from_date = graphene.DateTime(required=True)
        through_date = graphene.DateTime(required=True)
        inherits = graphene.List(graphene.Int)
        role = graphene.String(required=False)

    result = graphene.Field(AdminInvitationCodeCreateResult)

    @staticmethod
    @login_required
    @user_passes_test(fn_or(is_superuser, is_officer_role))
    def mutate(
        root, info, code, authority_id, from_date, through_date, inherits, role=None
    ):
        problems = []
        if code_problem := is_not_empty("code", code, "Code must not be empty"):
            problems.append(code_problem)

        if InvitationCode.objects.filter(code=code).exists():
            problems.append(
                AdminFieldValidationProblem(name="code", message="duplicate code")
            )

        if len(problems) > 0:
            return AdminInvitationCodeCreateMutation(
                result=AdminInvitationCodeCreateProblem(fields=problems)
            )
        user = info.context.user
        if user.is_authority_user:
            authority = info.context.user.authorityuser.authority

        if authority_id != 0:
            if not user.is_superuser:
                if user.is_staff:
                    check_permission_on_inherits_down(user, [authority_id])
                else:
                    check_permission_authority_must_be_the_same(user, [authority_id])

            authority = Authority.objects.get(pk=authority_id)

        invitation_code = InvitationCode.objects.create(
            code=code,
            authority=authority,
            from_date=from_date,
            through_date=through_date,
            role=role if role else AuthorityUser.Role.REPORTER,
        )
        return AdminInvitationCodeCreateMutation(result=invitation_code)


class AdminInvitationCodeUpdateMutation(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)
        code = graphene.String(required=True)
        from_date = graphene.DateTime(required=False)
        through_date = graphene.DateTime(required=False)
        role = graphene.String(required=False)

    result = graphene.Field(AdminInvitationCodeUpdateResult)

    @staticmethod
    @login_required
    @user_passes_test(fn_or(is_superuser, is_officer_role))
    def mutate(root, info, id, code, from_date, through_date, role):
        user = info.context.user

        try:
            invitation_code = InvitationCode.objects.get(pk=id)
        except InvitationCode.DoesNotExist:
            return AdminInvitationCodeUpdateMutation(
                result=AdminInvitationCodeUpdateProblem(
                    fields=[], message="Object not found"
                )
            )

        if not user.is_superuser:
            authority_id = invitation_code.authority_id
            if user.is_staff:
                check_permission_on_inherits_down(user, [authority_id])
            else:
                check_permission_authority_must_be_the_same(user, [authority_id])

        problems = []
        if invitation_code.code != code:
            if duplicate_problem := is_duplicate("code", code, InvitationCode):
                problems.append(duplicate_problem)

        if code_problem := is_not_empty("code", code, "Code must not be empty"):
            problems.append(code_problem)

        if len(problems) > 0:
            return AdminInvitationCodeUpdateMutation(
                result=AdminInvitationCodeUpdateProblem(fields=problems)
            )

        invitation_code.code = code
        if from_date is not None:
            invitation_code.from_date = from_date
        if through_date is not None:
            invitation_code.through_date = through_date
        if role is not None:
            invitation_code.role = role

        invitation_code.save()

        return AdminInvitationCodeUpdateMutation(
            result=AdminInvitationCodeUpdateSuccess(invitation_code=invitation_code)
        )


class AdminInvitationCodeDeleteMutation(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)

    success = graphene.Boolean()

    @staticmethod
    @login_required
    @superuser_required
    def mutate(root, info, id):
        code = InvitationCode.objects.get(pk=id)
        code.delete()
        return {"success": True}
