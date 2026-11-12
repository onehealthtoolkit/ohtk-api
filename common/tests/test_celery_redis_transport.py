"""Exercise the installed worker transport, beyond Redis socket readiness."""
import os
from uuid import uuid4

import pytest
from celery import Celery
from celery.contrib.testing.worker import start_worker


@pytest.mark.skipif(not os.getenv("CELERY_BROKER_URL"), reason="Redis broker required")
def test_redis_worker_round_trip():
    queue = f"ohtk-transport-test-{uuid4().hex}"
    app = Celery(
        queue,
        broker=os.environ["CELERY_BROKER_URL"],
        backend="cache+memory://",
        fixups=[],
    )
    app.conf.update(
        task_default_queue=queue,
        task_default_exchange=queue,
        task_default_routing_key=queue,
        task_always_eager=False,
    )

    @app.task(name=f"{queue}.echo")
    def echo(value):
        return value

    try:
        # Fail fast on an incompatible installed transport before starting a thread.
        with app.connection_for_write() as connection:
            connection.ensure_connection(max_retries=0)
            connection.channel().close()
        with start_worker(
            app, pool="solo", concurrency=1, perform_ping_check=False, shutdown_timeout=10
        ):
            assert echo.delay(queue).get(timeout=10) == queue
    finally:
        # Never consume or purge the application's default queue.
        try:
            with app.connection_for_write() as connection:
                connection.default_channel.queue_delete(queue)
        finally:
            app.close()
