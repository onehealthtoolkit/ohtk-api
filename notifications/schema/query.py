import graphene
from graphql_jwt.decorators import login_required

from notifications.models import UserMessage
from notifications.tasks import update_is_seen
from pagination import DjangoPaginationConnectionField

from notifications.schema.types import UserMessageType


class Query(graphene.ObjectType):
    my_messages = DjangoPaginationConnectionField(UserMessageType)
    my_message = graphene.Field(UserMessageType, id=graphene.String(required=True))

    @staticmethod
    @login_required
    def resolve_my_messages(root, info, **kwargs):
        user = info.context.user
        return UserMessage.objects.filter(user=user).order_by("-created_at")

    @staticmethod
    @login_required
    def resolve_my_message(root, info, id):
        user = info.context.user
        user_message = UserMessage.objects.get(user=user, id=id)
        update_is_seen.delay(id)
        return user_message
