import graphene

from outbreaks.schema.mutations import (
    AdminOutbreakPlanCreateMutation,
    AdminOutbreakPlanUpdateMutation,
    AdminOutbreakPlanDeleteMutation,
)


class Mutation(graphene.ObjectType):
    admin_outbreak_plan_create = AdminOutbreakPlanCreateMutation.Field()
    admin_outbreak_plan_update = AdminOutbreakPlanUpdateMutation.Field()
    admin_outbreak_plan_delete = AdminOutbreakPlanDeleteMutation.Field()
