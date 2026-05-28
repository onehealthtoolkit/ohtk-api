import graphene
from graphql import GraphQLError
from graphql_jwt.decorators import login_required, user_passes_test, superuser_required

from accounts.models import (
    AuthorityUser,
    Authority,
    User,
    Village,
    VillageReporterAssignment,
)
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
from accounts.village_capability import is_village_capability_enabled


class VillageReporterAssignmentInput(graphene.InputObjectType):
    village_id = graphene.Int(required=True)
    census_role = graphene.String(required=True)


def get_input_value(input_value, key):
    if hasattr(input_value, key):
        return getattr(input_value, key)
    return input_value.get(key)


def validate_village_assignments(authority, role, assignments, problems):
    if assignments is None:
        return None

    if role != AuthorityUser.Role.REPORTER:
        if assignments:
            problems.append(
                AdminFieldValidationProblem(
                    name="village_assignments",
                    message="village assignments require reporter role",
                )
            )
        return []

    if not is_village_capability_enabled():
        problems.append(
            AdminFieldValidationProblem(
                name="village_assignments", message="village capability is not enabled"
            )
        )
        return None

    valid_roles = set(VillageReporterAssignment.CensusRole.values)
    normalized_assignments = []
    village_ids = []
    seen_village_ids = set()

    for assignment in assignments:
        village_id = get_input_value(assignment, "village_id")
        census_role = get_input_value(assignment, "census_role")

        if village_id in seen_village_ids:
            problems.append(
                AdminFieldValidationProblem(
                    name="village_assignments",
                    message="village assignments contain duplicate village",
                )
            )
            continue
        seen_village_ids.add(village_id)
        village_ids.append(village_id)

        if census_role not in valid_roles:
            problems.append(
                AdminFieldValidationProblem(
                    name="village_assignments",
                    message="village assignments contain invalid census role",
                )
            )
        normalized_assignments.append((village_id, census_role))

    villages_by_id = {
        village.id: village for village in Village.objects.filter(id__in=village_ids)
    }
    missing_ids = [
        village_id for village_id in village_ids if village_id not in villages_by_id
    ]
    if missing_ids:
        problems.append(
            AdminFieldValidationProblem(
                name="village_assignments",
                message="village assignments contain unknown village",
            )
        )
        return None

    invalid_villages = [
        village
        for village in villages_by_id.values()
        if not authority.is_in_inherits_down([village.authority_id])
    ]
    if invalid_villages:
        problems.append(
            AdminFieldValidationProblem(
                name="village_assignments",
                message="village assignments must belong under reporter authority",
            )
        )
        return None

    if problems:
        return None

    return [
        (villages_by_id[village_id], census_role)
        for village_id, census_role in normalized_assignments
    ]


def replace_village_assignments(reporter, assignments):
    if assignments is None:
        return

    village_ids = {village.id for village, _ in assignments}
    for assignment in VillageReporterAssignment.objects.filter(reporter=reporter):
        if assignment.village_id not in village_ids:
            assignment.delete()

    for village, census_role in assignments:
        assignment, created = VillageReporterAssignment.objects.get_or_create(
            reporter=reporter,
            village=village,
            defaults={"census_role": census_role},
        )
        if not created and assignment.census_role != census_role:
            assignment.census_role = census_role
            assignment.save(update_fields=("census_role",))


class AdminAuthorityUserCreateMutation(graphene.Mutation):
    class Arguments:
        authority_id = graphene.Int(required=None)
        username = graphene.String(required=True)
        password = graphene.String(required=True)
        first_name = graphene.String(required=True)
        last_name = graphene.String(required=True)
        email = graphene.String(required=True)
        telephone = graphene.String(required=False)
        address = graphene.String(required=False)
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
        address,
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
            address=address,
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
        address = graphene.String(required=False)
        role = graphene.String(required=False)
        village_assignments = graphene.List(
            VillageReporterAssignmentInput, required=False
        )

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
        address,
        role,
        village_assignments=None,
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

        target_authority = update_user.authority
        if authority_id not in (None, 0):
            target_authority = Authority.objects.get(pk=authority_id)

        target_role = role if role is not None else update_user.role
        village_assignment_data = validate_village_assignments(
            target_authority, target_role, village_assignments, problems
        )

        if len(problems) > 0:
            return AdminAuthorityUserUpdateMutation(
                result=AdminAuthorityUserUpdateProblem(fields=problems)
            )

        update_user.authority = target_authority

        update_user.username = username
        update_user.first_name = first_name
        update_user.last_name = last_name
        update_user.email = email
        update_user.telephone = telephone
        update_user.address = address
        update_user.role = target_role
        update_user.save()
        if update_user.role != AuthorityUser.Role.REPORTER:
            replace_village_assignments(update_user, [])
        else:
            replace_village_assignments(update_user, village_assignment_data)
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
