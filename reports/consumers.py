from channels.exceptions import DenyConnection
from channels.generic.websocket import AsyncWebsocketConsumer

from common.utils import extract_jwt_payload_from_asgi_scope


def new_report_group_name(authority_id):
    return f"rp_{authority_id}"


class NewReportConsumers(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(args, kwargs)
        self.username = None
        self.authority_id = None
        self.group_name = None

    async def connect(self):
        self.authority_id = self.scope["url_route"]["kwargs"]["authority_id"]
        self.group_name = new_report_group_name(self.authority_id)
        payload = extract_jwt_payload_from_asgi_scope(self.scope)
        self.username = payload["username"]

        if self.username:
            await self.channel_layer.group_add(
                self.group_name,
                self.channel_name,
            )
            await self.accept()
        else:
            raise DenyConnection("invalid token")

    async def disconnect(self, code):
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name,
        )

    async def new_report(self, event):
        await self.send(text_data=event["text"])
