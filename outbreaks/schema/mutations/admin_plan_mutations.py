import graphene
from graphql_jwt.decorators import login_required, superuser_required

from outbreaks.models import Plan
from outbreaks.schema.types import (
    AdminOutbreakPlanCreateResult,
    AdminOutbreakPlanUpdateResult,
)


class AdminOutbreakPlanCreateMutation(graphene.Mutation):
    class Arguments:
        name = graphene.String(required=True)
        description = graphene.String(required=True)
        report_type_id = graphene.UUID(required=True)
        state_step_id = graphene.Int(required=True)
        zone1_color = graphene.String(required=False, default_value="")
        zone2_color = graphene.String(required=False, default_value="")
        zone3_color = graphene.String(required=False, default_value="")
        zone1_radius = graphene.Float(required=False, default_value=None)
        zone2_radius = graphene.Float(required=False, default_value=None)
        zone3_radius = graphene.Float(required=False, default_value=None)
        zone1_message_title = graphene.String(required=False, default_value="")
        zone2_message_title = graphene.String(required=False, default_value="")
        zone3_message_title = graphene.String(required=False, default_value="")
        zone1_message_body = graphene.String(required=False, default_value="")
        zone2_message_body = graphene.String(required=False, default_value="")
        zone3_message_body = graphene.String(required=False, default_value="")

    result = graphene.Field(AdminOutbreakPlanCreateResult)

    @staticmethod
    @login_required
    @superuser_required
    def mutate(
        root,
        info,
        name,
        description,
        report_type_id,
        state_step_id,
        zone1_color,
        zone2_color,
        zone3_color,
        zone1_radius,
        zone2_radius,
        zone3_radius,
        zone1_message_title,
        zone2_message_title,
        zone3_message_title,
        zone1_message_body,
        zone2_message_body,
        zone3_message_body,
    ):
        plan = Plan.objects.create(
            name=name,
            description=description,
            report_type_id=report_type_id,
            state_step_id=state_step_id,
            zone1_color=zone1_color,
            zone2_color=zone2_color,
            zone3_color=zone3_color,
            zone1_radius=zone1_radius,
            zone2_radius=zone2_radius,
            zone3_radius=zone3_radius,
            zone1_message_title=zone1_message_title,
            zone2_message_title=zone2_message_title,
            zone3_message_title=zone3_message_title,
            zone1_message_body=zone1_message_body,
            zone2_message_body=zone2_message_body,
            zone3_message_body=zone3_message_body,
        )
        return AdminOutbreakPlanCreateMutation(result=plan)


class AdminOutbreakPlanUpdateMutation(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)
        name = graphene.String(required=True)
        description = graphene.String(required=True)
        report_type_id = graphene.UUID(required=True)
        state_step_id = graphene.Int(required=True)
        zone1_color = graphene.String(required=False, default_value="")
        zone2_color = graphene.String(required=False, default_value="")
        zone3_color = graphene.String(required=False, default_value="")
        zone1_radius = graphene.Float(required=False, default_value=None)
        zone2_radius = graphene.Float(required=False, default_value=None)
        zone3_radius = graphene.Float(required=False, default_value=None)
        zone1_message_title = graphene.String(required=False, default_value="")
        zone2_message_title = graphene.String(required=False, default_value="")
        zone3_message_title = graphene.String(required=False, default_value="")
        zone1_message_body = graphene.String(required=False, default_value="")
        zone2_message_body = graphene.String(required=False, default_value="")
        zone3_message_body = graphene.String(required=False, default_value="")

    result = graphene.Field(AdminOutbreakPlanUpdateResult)

    @staticmethod
    @login_required
    @superuser_required
    def mutate(
        root,
        info,
        id,
        name,
        description,
        report_type_id,
        state_step_id,
        zone1_color,
        zone2_color,
        zone3_color,
        zone1_radius,
        zone2_radius,
        zone3_radius,
        zone1_message_title,
        zone2_message_title,
        zone3_message_title,
        zone1_message_body,
        zone2_message_body,
        zone3_message_body,
    ):
        plan = Plan.objects.get(id=id)
        plan.name = name
        plan.description = description
        plan.report_type_id = report_type_id
        plan.state_step_id = state_step_id
        plan.zone1_color = zone1_color
        plan.zone2_color = zone2_color
        plan.zone3_color = zone3_color
        plan.zone1_radius = zone1_radius
        plan.zone2_radius = zone2_radius
        plan.zone3_radius = zone3_radius
        plan.zone1_message_title = zone1_message_title
        plan.zone2_message_title = zone2_message_title
        plan.zone3_message_title = zone3_message_title
        plan.zone1_message_body = zone1_message_body
        plan.zone2_message_body = zone2_message_body
        plan.zone3_message_body = zone3_message_body
        plan.save()
        return AdminOutbreakPlanUpdateMutation(result=plan)


class AdminOutbreakPlanDeleteMutation(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)

    success = graphene.Boolean()

    @staticmethod
    @login_required
    @superuser_required
    def mutate(root, info, id):
        plan = Plan.objects.get(id=id)
        plan.delete()
        return {
            "success": True,
        }
