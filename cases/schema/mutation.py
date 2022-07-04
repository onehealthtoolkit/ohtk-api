import graphene

from .promote_to_case_mutation import PromoteToCaseMutation


class Mutation(graphene.ObjectType):
    promote_to_case = PromoteToCaseMutation.Field()
