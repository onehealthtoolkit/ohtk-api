from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from django.test import SimpleTestCase
from graphql_jwt.utils import jwt_encode

from podd_api.asgi import application
from threads.consumers import NewCommentConsumers, new_comment_group_name


async def _assert_thread_ws_flow(path, host, token, group_name):
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
                "type": "update.comment",
                "text": '{"thread_id":"updated"}',
            },
        )

        message = await communicator.receive_from(timeout=5)
        assert message == '{"thread_id":"updated"}'
    finally:
        if connected:
            await communicator.disconnect()


class ThreadWebsocketTests(SimpleTestCase):
    def test_thread_consumer_receives_group_message_via_redis_channel_layer(self):
        host = "tenant-ws-threads.opensur.test"
        thread_id = "thread1"
        tenant = SimpleNamespace(schema_name="tenant_ws_threads")
        token = jwt_encode({"username": "ws-thread-user", "authority_id": 9})

        with patch.object(
            NewCommentConsumers,
            "get_tenant_model",
            new=AsyncMock(return_value=tenant),
        ) as get_tenant_model:
            async_to_sync(_assert_thread_ws_flow)(
                f"/ws/comments/{thread_id}/",
                host,
                token,
                new_comment_group_name(tenant.schema_name, thread_id),
            )

        get_tenant_model.assert_awaited_once_with(host)
