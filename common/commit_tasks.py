from django.db import connection, transaction
from django_tenants.utils import schema_context


def after_commit(callback, *args, **kwargs):
    """Deferred work must see committed rows and retain the submitting tenant."""
    schema = connection.schema_name

    def run():
        with schema_context(schema):
            callback(*args, **kwargs)

    transaction.on_commit(run, robust=True)


def enqueue_after_commit(task, *args):
    after_commit(task.delay, *args)
