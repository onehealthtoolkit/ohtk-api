import json
import graphene
from graphql_jwt.decorators import login_required, user_passes_test

from accounts.utils import is_superuser
from common.utils import is_duplicate, is_not_empty
from reports.models.category import Category
from reports.models.report_type import ReportType

from reports.schema.types import (
    AdminReportTypeUpdateProblem,
    AdminReportTypeUpdateResult,
    AdminReportTypeUpdateSuccess,
)


class AdminReportTypeUpdateMutation(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)
        name = graphene.String(required=True)
        category_id = graphene.Int(required=True)
        definition = graphene.String(required=True)
        ordering = graphene.Int(required=True)
        state_definition_id = graphene.Int(required=False)
        renderer_data_template = graphene.String(required=False)
        followup_definition = graphene.String(required=False)
        renderer_followup_data_template = graphene.String(required=False)
        is_followable = graphene.Boolean(required=False, default_value=False)

    result = graphene.Field(AdminReportTypeUpdateResult)

    @staticmethod
    @login_required
    @user_passes_test(is_superuser)
    def mutate(
        root,
        info,
        id,
        name,
        category_id,
        definition,
        ordering,
        state_definition_id=None,
        renderer_data_template=None,
        followup_definition=None,
        renderer_followup_data_template=None,
        is_followable=False,
    ):
        try:
            report_type = ReportType.objects.get(pk=id)
        except ReportType.DoesNotExist:
            return AdminReportTypeUpdateMutation(
                result=AdminReportTypeUpdateProblem(
                    fields=[], message="Object not found"
                )
            )

        problems = []
        if name_problem := is_not_empty("name", name, "Name must not be empty"):
            problems.append(name_problem)

        if report_type.name != name:
            if dumplicate_problem := is_duplicate("name", name, ReportType):
                problems.append(dumplicate_problem)

        if len(problems) > 0:
            return AdminReportTypeUpdateMutation(
                result=AdminReportTypeUpdateProblem(fields=problems)
            )

        report_type.name = name
        report_type.category = Category.objects.get(pk=category_id)
        report_type.definition = json.loads(definition)
        report_type.ordering = ordering
        report_type.state_definition_id = state_definition_id
        report_type.renderer_data_template = renderer_data_template
        report_type.is_followable = is_followable

        if followup_definition:
            report_type.followup_definition = json.loads(followup_definition)
        else:
            report_type.followup_definition = None

        report_type.renderer_followup_data_template = renderer_followup_data_template
        report_type.save()
        return AdminReportTypeUpdateMutation(
            result=AdminReportTypeUpdateSuccess(report_type=report_type)
        )
