from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from django.test import SimpleTestCase
from graphql_jwt.utils import jwt_encode

from podd_api.asgi import application
from reports.consumers import NewReportConsumers, new_report_group_name


async def _assert_report_ws_flow(path, host, token, group_name):
    communicator = WebsocketCommunicator(
        application,
        path,
        headers=[
            (b"host", host.encode("ascii")),
            (b"cookie", f"JWT={token}".encode("ascii")),
        ],
    )
    connected = False

    try:
        connected, _ = await communicator.connect()
        assert connected

        await get_channel_layer().group_send(
            group_name,
            {
                "type": "new.report",
                "text": '{"event":"report-created"}',
            },
        )

        message = await communicator.receive_from(timeout=5)
        assert message == '{"event":"report-created"}'
    finally:
        if connected:
            await communicator.disconnect()


class ReportWebsocketTests(SimpleTestCase):
    def test_report_consumer_receives_group_message_via_redis_channel_layer(self):
        host = "tenant-ws-reports.opensur.test"
        authority_id = "7"
        tenant = SimpleNamespace(schema_name="tenant_ws_reports")
        token = jwt_encode({"username": "ws-report-user", "authority_id": 7})

        with patch.object(
            NewReportConsumers,
            "get_tenant_model",
            new=AsyncMock(return_value=tenant),
        ) as get_tenant_model:
            async_to_sync(_assert_report_ws_flow)(
                f"/ws/reports/{authority_id}/",
                host,
                token,
                new_report_group_name(tenant.schema_name, authority_id),
            )

        get_tenant_model.assert_awaited_once_with(host)
