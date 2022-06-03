import graphene

from accounts.models import AuthorityUser, Authority, User
from accounts.schema.types import (
    AdminAuthorityUserUpdateProblem,
    AdminAuthorityUserUpdateResult,
    AdminAuthorityUserCreateProblem,
    AdminAuthorityUserCreateResult,
    AdminFieldValidationProblem,
)


class AdminAuthorityUserCreateMutation(graphene.Mutation):
    class Arguments:
        authority_id = graphene.Int(required=True)
        username = graphene.String(required=True)
        password = graphene.String(required=True)
        first_name = graphene.String(required=True)
        last_name = graphene.String(required=True)
        email = graphene.String(required=True)
        telephone = graphene.String(required=False)

    result = graphene.Field(AdminAuthorityUserCreateResult)

    @staticmethod
    def mutate(
        root,
        info,
        authority_id,
        username,
        password,
        first_name,
        last_name,
        email,
        telephone,
    ):
        if User.objects.filter(username=username).exists():
            return AdminAuthorityUserCreateMutation(
                result=AdminAuthorityUserCreateProblem(
                    fields=[
                        AdminFieldValidationProblem(
                            name="username", message="duplicate username"
                        )
                    ]
                )
            )

        if not first_name:
            return AdminAuthorityUserCreateMutation(
                result=AdminAuthorityUserCreateProblem(
                    fields=[
                        AdminFieldValidationProblem(
                            name="first_name", message="first name must not be empty"
                        )
                    ]
                )
            )

        user = AuthorityUser.objects.create_user(
            authority=Authority.objects.get(pk=authority_id),
            username=username,
            password=password,
            first_name=first_name,
            last_name=last_name,
            email=email,
            telephone=telephone,
        )
        return AdminAuthorityUserCreateMutation(result=user)


class AdminAuthorityUserUpdateMutation(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)
        authority_id = graphene.Int(required=True)
        username = graphene.String(required=True)
        first_name = graphene.String(required=True)
        last_name = graphene.String(required=True)
        email = graphene.String(required=True)
        telephone = graphene.String(required=False)

    result = graphene.Field(AdminAuthorityUserUpdateResult)

    @staticmethod
    def mutate(
        root, info, id, authority_id, username, first_name, last_name, email, telephone
    ):
        print(id)
        print(authority_id)
        authorityUser = AuthorityUser.objects.get(pk=id)

        if not authorityUser:
            return AdminAuthorityUserUpdateMutation(
                result=AdminAuthorityUserUpdateProblem(
                    fields=[], message="Object not found"
                )
            )

        if (
            authorityUser.username != username
            and User.objects.filter(username=username).exists()
        ):
            return AdminAuthorityUserUpdateMutation(
                result=AdminAuthorityUserUpdateProblem(
                    fields=[
                        AdminFieldValidationProblem(
                            name="username", message="duplicate username"
                        )
                    ]
                )
            )

        if not first_name:
            return AdminAuthorityUserUpdateMutation(
                result=AdminAuthorityUserUpdateProblem(
                    fields=[
                        AdminFieldValidationProblem(
                            name="first_name", message="first name must not be empty"
                        )
                    ]
                )
            )

        authorityUser.authority = Authority.objects.get(pk=authority_id)
        authorityUser.username = username
        authorityUser.first_name = first_name
        authorityUser.last_name = last_name
        authorityUser.email = email
        authorityUser.telephone = telephone
        authorityUser.save()
        return AdminAuthorityUserUpdateMutation(result=authorityUser)
