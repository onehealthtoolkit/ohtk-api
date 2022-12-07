import graphene
from graphql_jwt.decorators import login_required, user_passes_test, superuser_required

from common.utils import is_duplicate, is_not_empty
from observations.models import Definition
from observations.schema.types import (
    AdminObservationDefinitionCreateProblem,
    AdminObservationDefinitionCreateResult,
    AdminObservationDefinitionUpdateProblem,
    AdminObservationDefinitionUpdateResult,
    AdminObservationDefinitionUpdateSuccess,
)

from accounts.utils import (
    check_permission_on_inherits_down,
    is_superuser,
    fn_and,
    is_staff,
    is_officer_role,
    fn_or,
)


class AdminObservationDefinitionCreateMutation(graphene.Mutation):
    """
    use to create a new observation definition
    """

    class Arguments:
        name = graphene.String(required=True)
        description = graphene.String(required=True)
        register_form_definition = graphene.JSONString(required=True)
        title_template = graphene.String(required=True)
        description_template = graphene.String(required=True)
        identity_template = graphene.String(required=True)

    result = graphene.Field(AdminObservationDefinitionCreateResult)

    @staticmethod
    @login_required
    @user_passes_test(fn_or(is_superuser, fn_and(is_staff, is_officer_role)))
    def mutate(
        self,
        info,
        name,
        description,
        register_form_definition,
        title_template,
        description_template,
        identity_template,
    ):
        problems = []

        if name_problem := is_not_empty("name", name, "Name must not be empty"):
            problems.append(name_problem)

        if duplicate_problem := is_duplicate("name", name, Definition):
            problems.append(duplicate_problem)

        if len(problems) > 0:
            return AdminObservationDefinitionCreateMutation(
                result=AdminObservationDefinitionCreateProblem(fields=problems)
            )

        definition = Definition.objects.create(
            name=name,
            description=description,
            register_form_definition=register_form_definition,
            title_template=title_template,
            description_template=description_template,
            identity_template=identity_template,
        )

        return AdminObservationDefinitionCreateMutation(result=definition)


class AdminObservationDefinitionUpdateMutation(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)
        name = graphene.String(required=True)
        description = graphene.String(required=True)
        register_form_definition = graphene.JSONString(required=True)
        title_template = graphene.String(required=True)
        description_template = graphene.String(required=True)
        identity_template = graphene.String(required=True)

    result = graphene.Field(AdminObservationDefinitionUpdateResult)

    @staticmethod
    @login_required
    @user_passes_test(fn_or(is_superuser, fn_and(is_staff, is_officer_role)))
    def mutate(
        root,
        info,
        id,
        name,
        description,
        register_form_definition,
        title_template,
        description_template,
        identity_template,
    ):

        user = info.context.user
        if not user.is_superuser:
            check_permission_on_inherits_down(
                user, [id]
            )  # allow to edit only sub child of their authority.

        try:
            definition = Definition.objects.get(pk=id)
        except Definition.DoesNotExist:
            return AdminObservationDefinitionUpdateMutation(
                result=AdminObservationDefinitionUpdateProblem(
                    fields=[], message="Object not found"
                )
            )

        problems = []
        if definition.name != name:
            if duplicate_problem := is_duplicate("name", name, Definition):
                problems.append(duplicate_problem)

        if name_problem := is_not_empty("name", name, "Name must not be empty"):
            problems.append(name_problem)

        if len(problems) > 0:
            return AdminObservationDefinitionUpdateMutation(
                result=AdminObservationDefinitionUpdateProblem(fields=problems)
            )

        definition.name = name

        definition.save()

        return AdminObservationDefinitionUpdateMutation(
            result=AdminObservationDefinitionUpdateSuccess(definition=definition)
        )


class AdminObservationDefinitionDeleteMutation(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)

    success = graphene.Boolean()

    @staticmethod
    @login_required
    @superuser_required
    def mutate(root, info, id):
        authority = Definition.objects.get(pk=id)
        authority.delete()
        return {"success": True}
