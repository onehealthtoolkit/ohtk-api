import json

from channels.exceptions import DenyConnection

from common.consumers import TenantConsumers
from common.utils import extract_jwt_payload_from_asgi_scope


def new_comment_group_name(schema_name, thread_id):
    return f"cm_{schema_name}_{thread_id}"


class NewCommentConsumers(TenantConsumers):
    def __init__(self, *args, **kwargs):
        self.username = None
        self.authority_id = None
        self.group_name = None
        super().__init__(*args, **kwargs)

    async def connect(self):
        thread_id = self.scope["url_route"]["kwargs"]["thread_id"]
        payload = extract_jwt_payload_from_asgi_scope(self.scope)
        self.username = payload["username"]
        self.authority_id = payload["authority_id"]
        try:
            await self.get_tenant()
        except ValueError as err:
            raise DenyConnection("domain not found")
        self.group_name = new_comment_group_name(self.tenant.schema_name, thread_id)

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

    async def update_comment(self, event):
        await self.send(text_data=event["text"])
