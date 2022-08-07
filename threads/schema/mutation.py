import graphene

from threads.schema.mutations.comment_create_mutation import CommentCreateMutation
from threads.schema.mutations.comment_delete_mutation import CommentDeleteMutation
from threads.schema.mutations.comment_update_mutation import CommentUpdateMutation


class Mutation(graphene.ObjectType):
    comment_create = CommentCreateMutation.Field()
    comment_update = CommentUpdateMutation.Field()
    comment_delete = CommentDeleteMutation.Field()
