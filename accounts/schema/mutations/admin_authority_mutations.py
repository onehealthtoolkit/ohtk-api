import graphene

from accounts.models import Authority
from accounts.schema.types import (
    AdminAuthorityCreateResult,
    AdminAuthorityUpdateResult,
    AdminAuthorityUpdateProblem,
    AdminAuthorityCreateProblem,
    AdminAuthorityUpdateSuccess,
)
from common.utils import is_duplicate, is_not_empty
from common.types import AdminFieldValidationProblem


class AdminAuthorityCreateMutation(graphene.Mutation):
    class Arguments:
        code = graphene.String(required=True)
        name = graphene.String(required=True)
        inherits = graphene.List(graphene.String)
        area = graphene.String(required=False)

    result = graphene.Field(AdminAuthorityCreateResult)

    @staticmethod
    def mutate(root, info, code, name, inherits, area=None):
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
    def mutate(root, info, id, code, name, inherits, area=None):
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
        if inherits:
            authority.inherits.set(Authority.objects.filter(pk__in=inherits))

        authority.save()

        return AdminAuthorityUpdateMutation(
            result=AdminAuthorityUpdateSuccess(authority=authority)
        )
