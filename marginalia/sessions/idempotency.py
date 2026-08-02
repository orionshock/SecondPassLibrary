from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
import hashlib
import json

from django.db import IntegrityError, transaction
from django.utils import timezone

from core.models import IdempotencyRecord


class IdempotencyConflictError(Exception):
    pass


class IdempotencyInProgressError(Exception):
    pass


def validate_idempotency_key(raw_key: str | None) -> str:
    key = (raw_key or "").strip()
    if not key or len(key) > 128:
        raise ValueError
    if any(ord(character) < 32 or ord(character) == 127 for character in key):
        raise ValueError
    return key


def normalized_request_hash(*, method: str, path: str, data: dict) -> str:
    body = json.dumps(data, sort_keys=True, separators=(",", ":"))
    value = f"{method}\n{path}\n{body}".encode()
    return hashlib.sha256(value).hexdigest()


@transaction.atomic
def execute_idempotent(
    *,
    user,
    key: str,
    method: str,
    path: str,
    request_hash: str,
    operation: Callable[[], dict],
) -> dict:
    now = timezone.now()
    record = (
        IdempotencyRecord.objects.select_for_update()
        .filter(user=user, key=key)
        .first()
    )
    if record is not None and record.expires_at <= now:
        record.delete()
        record = None

    if record is not None:
        return _replay(record, method=method, path=path, request_hash=request_hash)

    try:
        with transaction.atomic():
            record = IdempotencyRecord.objects.create(
                user=user,
                key=key,
                method=method,
                path=path,
                request_hash=request_hash,
                status=IdempotencyRecord.STATUS_PROCESSING,
                expires_at=now + timedelta(hours=24),
            )
    except IntegrityError:
        record = IdempotencyRecord.objects.select_for_update().get(user=user, key=key)
        return _replay(record, method=method, path=path, request_hash=request_hash)

    response_body = operation()
    record.status = IdempotencyRecord.STATUS_COMPLETED
    record.response_status = 201
    record.response_body = response_body
    record.save(
        update_fields=[
            "status",
            "response_status",
            "response_body",
            "updated_at",
        ]
    )
    return response_body


def _replay(
    record: IdempotencyRecord,
    *,
    method: str,
    path: str,
    request_hash: str,
) -> dict:
    if (
        record.method != method
        or record.path != path
        or record.request_hash != request_hash
    ):
        raise IdempotencyConflictError
    if (
        record.status != IdempotencyRecord.STATUS_COMPLETED
        or record.response_body is None
    ):
        raise IdempotencyInProgressError
    return record.response_body
