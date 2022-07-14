import graphene

from notifications.schema.mutations.register_fcm_token_mutation import (
    RegisterFcmTokenMutation,
)


class Mutation(graphene.ObjectType):
    register_fcm_token = RegisterFcmTokenMutation.Field()
