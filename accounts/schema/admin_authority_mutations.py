import graphene

from accounts.models import Authority
from accounts.schema.types import (
    AdminAuthorityCreateResult,
    AdminAuthorityUpdateResult,
    AdminAuthorityUpdateProblem,
    AdminAuthorityCreateProblem,
    AdminAuthorityUpdateSuccess,
)
from accounts.schema.utils import isDupliate, isNotEmpty
from common.types import AdminFieldValidationProblem


class AdminAuthorityCreateMutation(graphene.Mutation):
    class Arguments:
        code = graphene.String(required=True)
        name = graphene.String(required=True)
        inherits = graphene.List(graphene.String)

    result = graphene.Field(AdminAuthorityCreateResult)

    @staticmethod
    def mutate(root, info, code, name, inherits):
        problems = []
        if code_problem := isNotEmpty("code", "Code must not be empty"):
            problems.append(code_problem)

        if name_problem := isNotEmpty("name", "Name must not be empty"):
            problems.append(name_problem)

        if Authority.objects.filter(code=code).exists():
            problems.append(
                AdminFieldValidationProblem(name="code", message="duplicate code")
            )

        if len(problems) > 0:
            return AdminAuthorityCreateMutation(
                result=AdminAuthorityCreateProblem(fields=problems)
            )

        authority = Authority.objects.create(code=code, name=name)
        if inherits:
            authority.inherits.set(Authority.objects.filter(pk__in=inherits))

        return AdminAuthorityCreateMutation(result=authority)


class AdminAuthorityUpdateMutation(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)
        code = graphene.String(required=True)
        name = graphene.String(required=True)
        inherits = graphene.List(graphene.String)

    result = graphene.Field(AdminAuthorityUpdateResult)

    @staticmethod
    def mutate(root, info, id, code, name, inherits):
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
            if duplicateProblem := isDupliate("code", code, Authority):
                problems.append(duplicateProblem)

        if code_problem := isNotEmpty("code", "Code must not be empty"):
            problems.append(code_problem)

        if name_problem := isNotEmpty("name", "Name must not be empty"):
            problems.append(name_problem)

        if len(problems) > 0:
            return AdminAuthorityUpdateMutation(
                result=AdminAuthorityUpdateProblem(fields=problems)
            )

        authority.code = code
        authority.name = name
        if inherits:
            authority.inherits.set(Authority.objects.filter(pk__in=inherits))

        authority.save()

        return AdminAuthorityUpdateMutation(
            result=AdminAuthorityUpdateSuccess(authority=authority)
        )
