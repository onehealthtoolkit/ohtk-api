from channels.exceptions import DenyConnection

from common.consumers import TenantConsumers
from common.utils import extract_jwt_payload_from_asgi_scope


def new_report_group_name(schema_name, authority_id):
    return f"rp_{schema_name}_{authority_id}"


class NewReportConsumers(TenantConsumers):
    def __init__(self, *args, **kwargs):
        super().__init__(args, kwargs)
        self.username = None
        self.authority_id = None
        self.group_name = None

    async def connect(self):
        self.authority_id = self.scope["url_route"]["kwargs"]["authority_id"]
        await self.get_tenant()
        self.group_name = new_report_group_name(
            self.tenant.schema_name, self.authority_id
        )
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
