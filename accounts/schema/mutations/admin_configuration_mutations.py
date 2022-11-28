import graphene
from graphql import GraphQLError
from graphql_jwt.decorators import login_required, superuser_required

from accounts.models import AuthorityUser, Configuration
from accounts.utils import (
    check_permission_on_inherits_down,
    check_permission_authority_must_be_the_same,
)
from accounts.schema.types import (
    AdminConfigurationCreateResult,
    AdminConfigurationCreateProblem,
    AdminConfigurationUpdateResult,
    AdminConfigurationUpdateProblem,
)
from common.utils import is_not_empty


class AdminConfigurationCreateMutation(graphene.Mutation):
    class Arguments:
        key = graphene.String(required=True)
        value = graphene.String(required=True)

    result = graphene.Field(AdminConfigurationCreateResult)

    @staticmethod
    @login_required
    def mutate(root, info, key, value):
        problems = []
        if key_problem := is_not_empty("key", key, "Key must not be empty"):
            problems.append(key_problem)

        if value_problem := is_not_empty("value", key, "Value must not be empty"):
            problems.append(value_problem)

        if len(problems) > 0:
            return AdminConfigurationCreateMutation(
                result=AdminConfigurationCreateProblem(fields=problems)
            )

        # create configuration
        configuration = Configuration.objects.create(
            key=key,
            value=value,
        )

        return AdminConfigurationCreateMutation(result=configuration)


class AdminConfigurationUpdateMutation(graphene.Mutation):
    class Arguments:
        id = graphene.String(required=True)
        key = graphene.String(required=True)
        value = graphene.String(required=True)

    result = graphene.Field(AdminConfigurationUpdateResult)

    @staticmethod
    @login_required
    def mutate(root, info, id, key, value):
        try:
            update_configuration = Configuration.objects.get(pk=id)
        except Configuration.DoesNotExist:
            return AdminConfigurationUpdateMutation(
                result=AdminConfigurationUpdateProblem(
                    field=[], message="configuration does not exist"
                )
            )
        user = info.context.user

        if not user.is_superuser:
            if user.is_authority_role_in([AuthorityUser.Role.ADMIN]):
                check_permission_on_inherits_down(
                    user, [update_configuration.authority_id]
                )
            elif user.is_authority_role_in([AuthorityUser.Role.OFFICER]):
                check_permission_authority_must_be_the_same(
                    user, update_configuration.authority_id
                )
            else:
                raise GraphQLError("You don't have permission to update configuration")

        if key == id:
            update_configuration.value = value
            update_configuration.save()
        else:
            update_configuration.delete(hard=True)
            update_configuration = Configuration.objects.create(
                key=key,
                value=value,
            )
        return AdminConfigurationUpdateMutation(result=update_configuration)


class AdminConfigurationDeleteMutation(graphene.Mutation):
    class Arguments:
        id = graphene.String(required=True)

    success = graphene.Boolean()

    @staticmethod
    @login_required
    @superuser_required
    def mutate(root, info, id):
        configuration = Configuration.objects.get(pk=id)
        configuration.delete()
        return {"success": True}
