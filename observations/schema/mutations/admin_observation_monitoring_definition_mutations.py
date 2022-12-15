import graphene
from graphql_jwt.decorators import login_required, user_passes_test, superuser_required
from common.utils import is_duplicate, is_not_empty
from accounts.utils import (
    check_permission_on_inherits_down,
    is_superuser,
    fn_and,
    is_staff,
    is_officer_role,
    fn_or,
)
from observations.models import Definition, MonitoringDefinition
from observations.schema.types import (
    AdminObservationMonitoringDefinitionCreateProblem,
    AdminObservationMonitoringDefinitionCreateResult,
    AdminObservationMonitoringDefinitionUpdateProblem,
    AdminObservationMonitoringDefinitionUpdateResult,
    AdminObservationMonitoringDefinitionUpdateSuccess,
)


class AdminObservationMonitoringDefinitionCreateMutation(graphene.Mutation):
    class Arguments:
        definitionId = graphene.ID(required=True)
        name = graphene.String(required=True)
        description = graphene.String(required=True)
        form_definition = graphene.JSONString(required=True)
        title_template = graphene.String(required=True)
        description_template = graphene.String(required=True)

    result = graphene.Field(AdminObservationMonitoringDefinitionCreateResult)

    @staticmethod
    @login_required
    @user_passes_test(fn_or(is_superuser, fn_and(is_staff, is_officer_role)))
    def mutate(
        self,
        info,
        definitionId,
        name,
        description,
        form_definition,
        title_template,
        description_template,
    ):

        try:
            definition = Definition.objects.get(pk=definitionId)
        except MonitoringDefinition.DoesNotExist:
            return AdminObservationMonitoringDefinitionCreateMutation(
                result=AdminObservationMonitoringDefinitionCreateProblem(
                    fields=[], message="Definition not found"
                )
            )
        problems = []

        if name_problem := is_not_empty("name", name, "Name must not be empty"):
            problems.append(name_problem)

        if len(problems) > 0:
            return AdminObservationMonitoringDefinitionCreateMutation(
                result=AdminObservationMonitoringDefinitionCreateProblem(
                    fields=problems
                )
            )

        definition = MonitoringDefinition.objects.create(
            definition=definition,
            name=name,
            description=description,
            form_definition=form_definition,
            title_template=title_template,
            description_template=description_template,
        )

        return AdminObservationMonitoringDefinitionCreateMutation(result=definition)


class AdminObservationMonitoringDefinitionUpdateMutation(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)
        definitionId = graphene.ID(required=True)
        name = graphene.String(required=True)
        description = graphene.String(required=True)
        form_definition = graphene.JSONString(required=True)
        title_template = graphene.String(required=True)
        description_template = graphene.String(required=True)

    result = graphene.Field(AdminObservationMonitoringDefinitionUpdateResult)

    @staticmethod
    @login_required
    @user_passes_test(fn_or(is_superuser, fn_and(is_staff, is_officer_role)))
    def mutate(
        root,
        info,
        id,
        definitionId,
        name,
        description,
        form_definition,
        title_template,
        description_template,
    ):

        user = info.context.user
        if not user.is_superuser:
            check_permission_on_inherits_down(
                user, [id]
            )  # allow to edit only sub child of their authority.

        try:
            definition = Definition.objects.get(pk=definitionId)
        except MonitoringDefinition.DoesNotExist:
            return AdminObservationMonitoringDefinitionUpdateMutation(
                result=AdminObservationMonitoringDefinitionUpdateProblem(
                    fields=[], message="Definition not found"
                )
            )

        try:
            monitoring_definition = MonitoringDefinition.objects.get(pk=id)
        except MonitoringDefinition.DoesNotExist:
            return AdminObservationMonitoringDefinitionUpdateMutation(
                result=AdminObservationMonitoringDefinitionUpdateProblem(
                    fields=[], message="Object not found"
                )
            )

        problems = []
        if monitoring_definition.name != name:
            if duplicate_problem := is_duplicate("name", name, MonitoringDefinition):
                problems.append(duplicate_problem)

        if name_problem := is_not_empty("name", name, "Name must not be empty"):
            problems.append(name_problem)

        if len(problems) > 0:
            return AdminObservationMonitoringDefinitionUpdateMutation(
                result=AdminObservationMonitoringDefinitionUpdateProblem(
                    fields=problems
                )
            )

        monitoring_definition.definition = definition
        monitoring_definition.name = name
        monitoring_definition.description = description
        monitoring_definition.form_definition = form_definition
        monitoring_definition.title_template = title_template
        monitoring_definition.description_template = description_template

        monitoring_definition.save()

        return AdminObservationMonitoringDefinitionUpdateMutation(
            result=AdminObservationMonitoringDefinitionUpdateSuccess(
                monitoring_definition=monitoring_definition
            )
        )


class AdminObservationMonitoringDefinitionDeleteMutation(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)

    success = graphene.Boolean()

    @staticmethod
    @login_required
    @superuser_required
    def mutate(root, info, id):
        authority = MonitoringDefinition.objects.get(pk=id)
        authority.delete()
        return {"success": True}
