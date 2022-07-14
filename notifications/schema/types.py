import graphene
from graphene_django import DjangoObjectType

from accounts.models import User
from accounts.schema.types import UserType
from notifications.models import UserMessage, Message


class MessageType(DjangoObjectType):
    class Meta:
        model = Message
        fields = ["id", "title", "body", "image"]


class UserMessageType(DjangoObjectType):
    user = graphene.Field(UserType)
    message = graphene.Field(MessageType)

    class Meta:
        model = UserMessage
        fields = ["id", "message", "user", "is_seen"]
        filter_fields = {}
