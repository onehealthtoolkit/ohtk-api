import graphene

from threads.schema.mutations.comment_create_mutation import CommentCreateMutation


class Mutation(graphene.ObjectType):
    comment_create = CommentCreateMutation.Field()
