import graphene

from accounts.models import Authority
from accounts.schema.types import (
    AdminAuthorityCreateResult,
    AdminFieldValidationProblem,
    AdminAuthorityUpdateResult,
    AdminAuthorityUpdateProblem,
    AdminAuthorityCreateProblem,
)


class AdminAuthorityCreateMutation(graphene.Mutation):
    class Arguments:
        code = graphene.String(required=True)
        name = graphene.String(required=True)

    result = graphene.Field(AdminAuthorityCreateResult)

    @staticmethod
    def mutate(root, info, code, name):
        if Authority.objects.filter(code=code).exists():
            return AdminAuthorityCreateMutation(
                result=AdminAuthorityCreateProblem(
                    fields=[
                        AdminFieldValidationProblem(
                            name="code", message="duplicate code"
                        )
                    ]
                )
            )

        if not name:
            return AdminAuthorityCreateMutation(
                result=AdminAuthorityCreateProblem(
                    fields=[
                        AdminFieldValidationProblem(
                            name="name", message="name must not be empty"
                        )
                    ]
                )
            )

        authority = Authority.objects.create(code=code, name=name)
        return AdminAuthorityCreateMutation(result=authority)


class AdminAuthorityUpdateMutation(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)
        code = graphene.String(required=True)
        name = graphene.String(required=True)

    result = graphene.Field(AdminAuthorityUpdateResult)

    @staticmethod
    def mutate(root, info, id, code, name):
        authority = Authority.objects.get(pk=id)

        if not authority:
            return AdminAuthorityUpdateMutation(
                result=AdminAuthorityUpdateProblem(
                    fields=[], message="Object not found"
                )
            )

        if authority.code != code and Authority.objects.filter(code=code).exists():
            return AdminAuthorityUpdateMutation(
                result=AdminAuthorityUpdateProblem(
                    fields=[
                        AdminFieldValidationProblem(
                            name="code", message="duplicate code"
                        )
                    ]
                )
            )

        if not name:
            return AdminAuthorityUpdateMutation(
                result=AdminAuthorityUpdateProblem(
                    fields=[
                        AdminFieldValidationProblem(
                            name="name", message="name must not be empty"
                        )
                    ]
                )
            )

        authority.code = code
        authority.name = name
        authority.save()

        return {"result": authority}
