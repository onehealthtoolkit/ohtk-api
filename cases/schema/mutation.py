import graphene
from .mutations import (
    AdminCaseDefinitionCreateMutation,
    AdminCaseDefinitionUpdateMutation,
    PromoteToCaseMutation,
)


class Mutation(graphene.ObjectType):
    promote_to_case = PromoteToCaseMutation.Field()
    admin_case_definition_create = AdminCaseDefinitionCreateMutation.Field()
    admin_case_definition_update = AdminCaseDefinitionUpdateMutation.Field()
