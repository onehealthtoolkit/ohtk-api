import graphene
from django.core.exceptions import PermissionDenied
from graphql_jwt.decorators import login_required, user_passes_test, superuser_required

from accounts.models import Authority
from accounts.schema.types import (
    AdminAuthorityCreateResult,
    AdminAuthorityUpdateResult,
    AdminAuthorityUpdateProblem,
    AdminAuthorityCreateProblem,
    AdminAuthorityUpdateSuccess,
)
from accounts.utils import (
    check_permission_on_inherits_down,
    is_superuser,
    fn_and,
    is_staff,
    is_officer_role,
    fn_or,
)
from common.types import AdminFieldValidationProblem
from common.utils import is_duplicate, is_not_empty


class AdminAuthorityCreateMutation(graphene.Mutation):
    class Arguments:
        code = graphene.String(required=True)
        name = graphene.String(required=True)
        inherits = graphene.List(graphene.String)
        area = graphene.String(required=False)

    result = graphene.Field(AdminAuthorityCreateResult)

    @staticmethod
    @login_required
    @user_passes_test(fn_or(is_superuser, fn_and(is_staff, is_officer_role)))
    def mutate(root, info, code, name, inherits, area=None):
        user = info.context.user
        if not user.is_superuser:
            check_permission_on_inherits_down(user, inherits)

        problems = []
        if code_problem := is_not_empty("code", code, "Code must not be empty"):
            problems.append(code_problem)

        if name_problem := is_not_empty("name", name, "Name must not be empty"):
            problems.append(name_problem)

        if Authority.objects.filter(code=code).exists():
            problems.append(
                AdminFieldValidationProblem(name="code", message="duplicate code")
            )

        if len(problems) > 0:
            return AdminAuthorityCreateMutation(
                result=AdminAuthorityCreateProblem(fields=problems)
            )

        authority = Authority.objects.create(code=code, name=name, area=area)
        if inherits:
            authority.inherits.set(Authority.objects.filter(pk__in=inherits))

        return AdminAuthorityCreateMutation(result=authority)


class AdminAuthorityUpdateMutation(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)
        code = graphene.String(required=True)
        name = graphene.String(required=True)
        inherits = graphene.List(graphene.String)
        area = graphene.String(required=False)

    result = graphene.Field(AdminAuthorityUpdateResult)

    @staticmethod
    @login_required
    @user_passes_test(fn_or(is_superuser, fn_and(is_staff, is_officer_role)))
    def mutate(root, info, id, code, name, inherits, area=None):
        user = info.context.user
        if not user.is_superuser:
            check_permission_on_inherits_down(
                user, [id]
            )  # allow to edit only sub child of their authority.

        try:
            authority = Authority.objects.get(pk=id)
        except Authority.DoesNotExist:
            return AdminAuthorityUpdateMutation(
                result=AdminAuthorityUpdateProblem(
                    fields=[], message="Object not found"
                )
            )

        problems = []
        if authority.code != code:
            if duplicate_problem := is_duplicate("code", code, Authority):
                problems.append(duplicate_problem)

        if code_problem := is_not_empty("code", code, "Code must not be empty"):
            problems.append(code_problem)

        if name_problem := is_not_empty("name", name, "Name must not be empty"):
            problems.append(name_problem)

        if len(problems) > 0:
            return AdminAuthorityUpdateMutation(
                result=AdminAuthorityUpdateProblem(fields=problems)
            )

        authority.code = code
        authority.name = name
        if area:
            authority.area = area
        if inherits != None:
            authority.inherits.set(Authority.objects.filter(pk__in=inherits))

        authority.save()

        return AdminAuthorityUpdateMutation(
            result=AdminAuthorityUpdateSuccess(authority=authority)
        )


class AdminAuthorityDeleteMutation(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)

    success = graphene.Boolean()

    @staticmethod
    @login_required
    @superuser_required
    def mutate(root, info, id):
        authority = Authority.objects.get(pk=id)
        authority.delete()
        return {"success": True}
