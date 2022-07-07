import graphene
from accounts.models import Authority, InvitationCode

from accounts.schema.types import (
    AdminInvitationCodeCreateResult,
    AdminInvitationCodeUpdateResult,
    AdminInvitationCodeUpdateProblem,
    AdminInvitationCodeCreateProblem,
    AdminInvitationCodeUpdateSuccess,
)
from accounts.schema.utils import is_duplicate, is_not_empty
from common.types import AdminFieldValidationProblem


class AdminInvitationCodeCreateMutation(graphene.Mutation):
    class Arguments:
        code = graphene.String(required=True)
        authority_id = graphene.Int(required=True)
        from_date = graphene.DateTime(required=True)
        through_date = graphene.DateTime(required=True)
        inherits = graphene.List(graphene.Int)

    result = graphene.Field(AdminInvitationCodeCreateResult)

    @staticmethod
    def mutate(root, info, code, authority_id, from_date, through_date, inherits):
        problems = []
        if code_problem := is_not_empty("code", "Code must not be empty"):
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
        if user.is_authority_user():
            authority = info.context.user.authorityuser.authority
        if authority_id != 0:
            authority = Authority.objects.get(pk=authority_id)

        invitation_code = InvitationCode.objects.create(
            code=code,
            authority=authority,
            from_date=from_date,
            through_date=through_date,
        )
        return AdminInvitationCodeCreateMutation(result=invitation_code)


class AdminInvitationCodeUpdateMutation(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)
        code = graphene.String(required=True)
        from_date = graphene.DateTime(required=None)
        through_date = graphene.DateTime(required=None)

    result = graphene.Field(AdminInvitationCodeUpdateResult)

    @staticmethod
    def mutate(root, info, id, code, from_date, through_date):
        try:
            invitation_code = InvitationCode.objects.get(pk=id)
        except InvitationCode.DoesNotExist:
            return AdminInvitationCodeUpdateMutation(
                result=AdminInvitationCodeUpdateProblem(
                    fields=[], message="Object not found"
                )
            )

        problems = []
        if invitation_code.code != code:
            if duplicate_problem := is_duplicate("code", code, InvitationCode):
                problems.append(duplicate_problem)

        if code_problem := is_not_empty("code", "Code must not be empty"):
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

        invitation_code.save()

        return AdminInvitationCodeUpdateMutation(
            result=AdminInvitationCodeUpdateSuccess(invitation_code=invitation_code)
        )
