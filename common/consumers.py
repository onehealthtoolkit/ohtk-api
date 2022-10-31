from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from tenants.models import Domain


class TenantConsumers(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        self.tenant = None
        super().__init__(*args, **kwargs)

    async def get_tenant(self):
        if "headers" not in self.scope:
            raise ValueError("this method should use only in asgi scope")

        for key, value in self.scope.get("headers", []):
            if key == b"host":
                host_name = value.decode("ascii")
                break
        else:
            raise ValueError("The headers key in the scope is invalid.")
        self.tenant = await self.get_tenant_model(host_name)

    @database_sync_to_async
    def get_tenant_model(self, host_name):
        try:
            domain = Domain.objects.get(domain=host_name)
        except Domain.DoesNotExist:
            raise ValueError("domain not found")
        return domain.tenant
