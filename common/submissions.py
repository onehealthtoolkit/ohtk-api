"""Tenant-scoped submission serialization and immutable attachment replay."""
from contextlib import contextmanager
import hashlib
import logging
from pathlib import Path
import uuid

from django.contrib.contenttypes.models import ContentType
from django.core.files import File
from django.db import connection, transaction
from graphql import GraphQLError

logger = logging.getLogger(__name__)


def conflict():
    return GraphQLError(
        "Submission ID is unavailable for this request.",
        extensions={"code": "SUBMISSION_CONFLICT"},
    )


@contextmanager
def submission_transaction(model, submission_id):
    """Lock absent as well as existing rows, shared by every writer of a model.

    The UUID primary key remains the final constraint. A deterministic advisory
    lock avoids writing storage files (or child rows) before a competing INSERT
    has committed. Include schema, not actor or endpoint, in the lock namespace.
    """
    with transaction.atomic():
        if submission_id is not None:
            key = f"{connection.schema_name}:{model._meta.label_lower}:{submission_id}"
            lock_id = int.from_bytes(
                hashlib.sha256(key.encode()).digest()[:8], byteorder="big", signed=True
            )
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(%s)", [lock_id])
        yield


def replay(model, submission_id, **bindings):
    """Check deleted rows too: a deleted UUID must never be silently reused."""
    if submission_id is None:
        return None
    existing = model._base_manager.filter(pk=submission_id).first()
    if existing is not None:
        if existing.deleted_at is not None or any(
            getattr(existing, field) != value for field, value in bindings.items()
        ):
            raise conflict()
    return existing


def submit_attachment(
    model,
    parent,
    relation,
    upload,
    attachment_id=None,
    *,
    validate=None,
    is_cover=False,
):
    instance = None
    try:
        with submission_transaction(model, attachment_id):
            parent = type(parent).objects.select_for_update().get(pk=parent.pk)
            bindings = {
                f"{relation}_type_id": ContentType.objects.get_for_model(parent).pk,
                f"{relation}_id": parent.pk,
            }
            existing = replay(model, attachment_id, **bindings)
            if existing is not None:
                return existing
            metadata = validate(upload) if validate else {}
            # S3 can overwrite equal names. Each attempt owns a distinct storage
            # key, so rollback cleanup cannot delete another tenant's file.
            storage_name = f"{uuid.uuid4().hex}_{Path(upload.name).name}"
            instance = model(
                id=attachment_id or uuid.uuid4(),
                file=File(upload, name=storage_name),
                **bindings,
                **metadata,
            )
            instance.save(force_insert=True)
            if is_cover:
                # Only the initial accepted upload sets cover. Avoid re-running
                # parent rendering (SubjectRecord.save ignores update_fields).
                type(parent).objects.filter(pk=parent.pk).update(
                    cover_image_id=instance.pk
                )
        return instance
    except Exception:
        if instance is not None and instance.file._committed:
            try:
                # Also protects an uncertain commit outcome: retain a referenced
                # file rather than turning an accepted row into a broken upload.
                if not model._base_manager.filter(file=instance.file.name).exists():
                    instance.file.storage.delete(instance.file.name)
            except Exception:
                logger.exception("Could not clean up an unaccepted attachment")
        raise
