import graphene
from graphql import GraphQLError
from graphql_jwt.decorators import login_required, user_passes_test, superuser_required

from accounts.models import AuthorityUser, Authority, User
from accounts.schema.types import (
    AdminAuthorityUserUpdateProblem,
    AdminAuthorityUserUpdateResult,
    AdminAuthorityUserCreateProblem,
    AdminAuthorityUserCreateResult,
    AdminAuthorityUserUpdateSuccess,
)
from accounts.utils import (
    check_permission_on_inherits_down,
    check_permission_authority_must_be_the_same,
    fn_or,
    is_superuser,
    is_officer_role,
)
from common.types import AdminFieldValidationProblem
from common.utils import is_duplicate, is_not_empty


class AdminAuthorityUserCreateMutation(graphene.Mutation):
    class Arguments:
        authority_id = graphene.Int(required=None)
        username = graphene.String(required=True)
        password = graphene.String(required=True)
        first_name = graphene.String(required=True)
        last_name = graphene.String(required=True)
        email = graphene.String(required=True)
        telephone = graphene.String(required=False)
        role = graphene.String(required=False)

    result = graphene.Field(AdminAuthorityUserCreateResult)

    @staticmethod
    @login_required
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
        role,
    ):
        user = info.context.user
        if not user.is_superuser:
            if authority_id:
                if user.is_authority_role_in([AuthorityUser.Role.ADMIN]):
                    check_permission_on_inherits_down(authority_id)
                elif user.is_authority_role_in([AuthorityUser.Role.OFFICER]):
                    check_permission_authority_must_be_the_same(user, authority_id)
                else:
                    raise GraphQLError("Permission denied")
            else:
                authority_id = user.authorityuser.authority_id

        problems = []
        if username_problem := is_not_empty(
            "username", username, "User name must not be empty"
        ):
            problems.append(username_problem)

        if first_name_problem := is_not_empty(
            "first_name", first_name, "First name must not be empty"
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

        authority = Authority.objects.get(pk=authority_id)
        user = AuthorityUser.objects.create_user(
            authority=authority,
            username=username,
            password=password,
            first_name=first_name,
            last_name=last_name,
            email=email,
            telephone=telephone,
            role=role,
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
        role = graphene.String(required=False)

    result = graphene.Field(AdminAuthorityUserUpdateResult)

    @staticmethod
    @login_required
    def mutate(
        root,
        info,
        id,
        authority_id,
        username,
        first_name,
        last_name,
        email,
        telephone,
        role,
    ):
        try:
            update_user = AuthorityUser.objects.get(pk=id)
        except AuthorityUser.DoesNotExist:
            return AdminAuthorityUserUpdateMutation(
                result=AdminAuthorityUserUpdateProblem(
                    fields=[], message="Object not found"
                )
            )
        user = info.context.user

        if not user.is_superuser:
            if user.is_authority_role_in([AuthorityUser.Role.ADMIN]):
                check_permission_on_inherits_down(user, [update_user.authority_id])
            elif user.is_authority_role_in([AuthorityUser.Role.OFFICER]):
                check_permission_authority_must_be_the_same(
                    user, update_user.authority_id
                )
            else:
                raise GraphQLError("Permission denied.")

        problems = []
        if update_user.username != username:
            if duplicate_problem := is_duplicate("username", username, AuthorityUser):
                problems.append(duplicate_problem)

        if username_problem := is_not_empty(
            "username", username, "User name must not be empty"
        ):
            problems.append(username_problem)

        if first_name_problem := is_not_empty(
            "first_name", first_name, "First name must not be empty"
        ):
            problems.append(first_name_problem)

        if len(problems) > 0:
            return AdminAuthorityUserUpdateMutation(
                result=AdminAuthorityUserUpdateProblem(fields=problems)
            )
        if (
            update_user.username != username
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
            update_user.authority = Authority.objects.get(pk=authority_id)

        update_user.username = username
        update_user.first_name = first_name
        update_user.last_name = last_name
        update_user.email = email
        update_user.telephone = telephone
        update_user.role = role
        update_user.save()
        return AdminAuthorityUserUpdateMutation(
            result=AdminAuthorityUserUpdateSuccess(authority_user=update_user)
        )


class AdminAuthorityUserUpdatePasswordMutation(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)
        password = graphene.String(required=True)

    result = graphene.Field(AdminAuthorityUserUpdateResult)

    @staticmethod
    @login_required
    def mutate(
        root,
        info,
        id,
        password,
    ):
        try:
            update_user = AuthorityUser.objects.get(pk=id)
        except AuthorityUser.DoesNotExist:
            return AdminAuthorityUserUpdateMutation(
                result=AdminAuthorityUserUpdateProblem(
                    fields=[], message="Object not found"
                )
            )
        user = info.context.user

        if not user.is_superuser:
            if user.is_authority_role_in([AuthorityUser.Role.ADMIN]):
                check_permission_on_inherits_down(user, [update_user.authority_id])
            elif user.is_authority_role_in([AuthorityUser.Role.OFFICER]):
                check_permission_authority_must_be_the_same(
                    user, update_user.authority_id
                )
            else:
                raise GraphQLError("Permission denied.")

        problems = []

        if password_problem := is_not_empty(
            "password", password, "Password must not be empty"
        ):
            problems.append(password_problem)

        if len(problems) > 0:
            return AdminAuthorityUserUpdateMutation(
                result=AdminAuthorityUserUpdateProblem(fields=problems)
            )

        update_user.set_password(password)
        update_user.save(update_fields=("password",))
        update_user.save()
        return AdminAuthorityUserUpdateMutation(
            result=AdminAuthorityUserUpdateSuccess(authority_user=update_user)
        )


class AdminAuthorityUserDeleteMutation(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)

    success = graphene.Boolean()

    @staticmethod
    @login_required
    def mutate(root, info, id):
        user = info.context.user
        delete_user = AuthorityUser.objects.get(pk=id)
        if not user.is_superuser:
            if user.is_authority_role_in([AuthorityUser.Role.ADMIN]):
                check_permission_on_inherits_down(user, [delete_user.authority_id])
            elif user.is_authority_role_in([AuthorityUser.Role.OFFICER]):
                check_permission_authority_must_be_the_same(
                    user, delete_user.authority_id
                )
            else:
                raise GraphQLError("Permission denied.")

        delete_user.is_active = False
        delete_user.save(update_fields=("is_active",))
        return {"success": True}
