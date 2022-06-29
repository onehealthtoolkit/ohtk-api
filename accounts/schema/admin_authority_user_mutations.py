import graphene

from accounts.models import AuthorityUser, Authority, User
from accounts.schema.types import (
    AdminAuthorityUserUpdateProblem,
    AdminAuthorityUserUpdateResult,
    AdminAuthorityUserCreateProblem,
    AdminAuthorityUserCreateResult,
    AdminAuthorityUserUpdateSuccess,
)
from accounts.schema.utils import isDupliate, isNotEmpty
from common.types import AdminFieldValidationProblem


class AdminAuthorityUserCreateMutation(graphene.Mutation):
    class Arguments:
        authority_id = graphene.Int(required=None)
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
        problems = []
        if username_problem := isNotEmpty("username", "User name must not be empty"):
            problems.append(username_problem)

        if first_name_problem := isNotEmpty(
            "first_name", "First name must not be empty"
        ):
            problems.append(first_name_problem)

        if User.objects.filter(username=username).exists():
            problems.append(
                AdminFieldValidationProblem(
                    name="username", message="duplicate username"
                )
            )

        if len(problems) > 0:
            return AdminAuthorityUserCreateMutation(
                result=AdminAuthorityUserCreateProblem(fields=problems)
            )

        user = info.context.user
        if hasattr(user, "authorityuser"):
            authority = info.context.user.authorityuser.authority
        if authority_id != 0:
            authority = Authority.objects.get(pk=authority_id)

        user = AuthorityUser.objects.create_user(
            authority=authority,
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
        authority_id = graphene.Int(required=None)
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
        try:
            authority_user = AuthorityUser.objects.get(pk=id)
        except AuthorityUser.DoesNotExist:
            return AdminAuthorityUserUpdateMutation(
                result=AdminAuthorityUserUpdateProblem(
                    fields=[], message="Object not found"
                )
            )

        problems = []
        if authority_user.username != username:
            if duplicate_problem := isDupliate("username", username, AuthorityUser):
                problems.append(duplicate_problem)

        if username_problem := isNotEmpty("username", "User name must not be empty"):
            problems.append(username_problem)

        if first_name_problem := isNotEmpty(
            "first_name", "First name must not be empty"
        ):
            problems.append(first_name_problem)

        if len(problems) > 0:
            return AdminAuthorityUserUpdateMutation(
                result=AdminAuthorityUserUpdateProblem(fields=problems)
            )
        if (
            authority_user.username != username
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
        if authority_id != 0:
            authority_user.authority = Authority.objects.get(pk=authority_id)

        authority_user.username = username
        authority_user.first_name = first_name
        authority_user.last_name = last_name
        authority_user.email = email
        authority_user.telephone = telephone
        authority_user.save()
        return AdminAuthorityUserUpdateMutation(
            result=AdminAuthorityUserUpdateSuccess(authority_user=authority_user)
        )
