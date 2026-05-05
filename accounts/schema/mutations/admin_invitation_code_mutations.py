import graphene
from graphql import GraphQLError
from graphql_jwt.decorators import login_required, user_passes_test, superuser_required

from accounts.models import Authority, InvitationCode, AuthorityUser, Village

from accounts.schema.types import (
    AdminInvitationCodeCreateResult,
    AdminInvitationCodeUpdateResult,
    AdminInvitationCodeUpdateProblem,
    AdminInvitationCodeCreateProblem,
    AdminInvitationCodeUpdateSuccess,
)
from accounts.village_capability import is_village_capability_enabled
from accounts.utils import (
    fn_or,
    is_superuser,
    is_officer_role,
    check_permission_on_inherits_down,
    check_permission_authority_must_be_the_same,
)
from common.utils import is_duplicate, is_not_empty
from common.types import AdminFieldValidationProblem


def get_invitation_villages(authority, village_ids, role, problems):
    if not village_ids:
        return []

    if role != AuthorityUser.Role.REPORTER:
        problems.append(
            AdminFieldValidationProblem(
                name="role", message="village invitations require reporter role"
            )
        )
        return []

    unique_village_ids = list(dict.fromkeys(village_ids))
    if not is_village_capability_enabled():
        problems.append(
            AdminFieldValidationProblem(
                name="village_ids", message="village capability is not enabled"
            )
        )
        return []

    villages = list(Village.objects.filter(id__in=unique_village_ids))
    found_ids = {village.id for village in villages}
    missing_ids = [
        village_id for village_id in unique_village_ids if village_id not in found_ids
    ]
    if missing_ids:
        problems.append(
            AdminFieldValidationProblem(
                name="village_ids", message="village_ids contain unknown village"
            )
        )
        return []

    invalid_villages = [
        village
        for village in villages
        if not authority.is_in_inherits_down([village.authority_id])
    ]
    if invalid_villages:
        problems.append(
            AdminFieldValidationProblem(
                name="village_ids",
                message="village_ids must belong under invitation authority",
            )
        )
        return []

    return villages


class AdminInvitationCodeCreateMutation(graphene.Mutation):
    class Arguments:
        code = graphene.String(required=True)
        authority_id = graphene.Int(required=True)
        from_date = graphene.DateTime(required=True)
        through_date = graphene.DateTime(required=True)
        inherits = graphene.List(graphene.Int)
        role = graphene.String(required=False)
        village_ids = graphene.List(graphene.Int, required=False)

    result = graphene.Field(AdminInvitationCodeCreateResult)

    @staticmethod
    @login_required
    def mutate(
        root,
        info,
        code,
        authority_id,
        from_date,
        through_date,
        inherits,
        role=None,
        village_ids=None,
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
                if user.is_authority_role_in([AuthorityUser.Role.ADMIN]):
                    check_permission_on_inherits_down(user, [authority_id])
                elif user.is_authority_role_in([AuthorityUser.Role.OFFICER]):
                    check_permission_authority_must_be_the_same(user, authority_id)
                else:
                    raise GraphQLError(
                        "You are not authorized to create invitation code"
                    )
            authority = Authority.objects.get(pk=authority_id)

        invitation_role = role if role else AuthorityUser.Role.REPORTER
        villages = get_invitation_villages(
            authority, village_ids, invitation_role, problems
        )
        if len(problems) > 0:
            return AdminInvitationCodeCreateMutation(
                result=AdminInvitationCodeCreateProblem(fields=problems)
            )

        invitation_code = InvitationCode.objects.create(
            code=code,
            authority=authority,
            from_date=from_date,
            through_date=through_date,
            role=invitation_role,
        )
        invitation_code.villages.set(villages)
        return AdminInvitationCodeCreateMutation(result=invitation_code)


class AdminInvitationCodeUpdateMutation(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)
        code = graphene.String(required=True)
        authority_id = graphene.Int(required=False)
        from_date = graphene.DateTime(required=False)
        through_date = graphene.DateTime(required=False)
        role = graphene.String(required=False)
        village_ids = graphene.List(graphene.Int, required=False)

    result = graphene.Field(AdminInvitationCodeUpdateResult)

    @staticmethod
    @login_required
    def mutate(
        root,
        info,
        id,
        code,
        authority_id=None,
        from_date=None,
        through_date=None,
        role=None,
        village_ids=None,
    ):
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
            if user.is_authority_role_in([AuthorityUser.Role.ADMIN]):
                check_permission_on_inherits_down(user, [invitation_code.authority_id])
            elif user.is_authority_role_in([AuthorityUser.Role.OFFICER]):
                check_permission_authority_must_be_the_same(
                    user, invitation_code.authority_id
                )
            else:
                raise GraphQLError("Permission denied.")

        problems = []
        if invitation_code.code != code:
            if duplicate_problem := is_duplicate("code", code, InvitationCode):
                problems.append(duplicate_problem)

        if code_problem := is_not_empty("code", code, "Code must not be empty"):
            problems.append(code_problem)

        target_authority = invitation_code.authority
        if authority_id:
            target_authority = Authority.objects.get(pk=authority_id)

        effective_role = role if role is not None else invitation_code.role
        villages = None
        if village_ids is not None:
            villages = get_invitation_villages(
                target_authority, village_ids, effective_role, problems
            )
        elif (
            effective_role != AuthorityUser.Role.REPORTER
            and invitation_code.villages.exists()
        ):
            problems.append(
                AdminFieldValidationProblem(
                    name="role", message="village invitations require reporter role"
                )
            )

        if len(problems) > 0:
            return AdminInvitationCodeUpdateMutation(
                result=AdminInvitationCodeUpdateProblem(fields=problems)
            )

        invitation_code.code = code
        if authority_id:
            invitation_code.authority = target_authority
        if from_date is not None:
            invitation_code.from_date = from_date
        if through_date is not None:
            invitation_code.through_date = through_date
        if role is not None:
            invitation_code.role = role

        invitation_code.save()
        if villages is not None:
            invitation_code.villages.set(villages)

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
