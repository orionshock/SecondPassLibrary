from __future__ import annotations

from collections.abc import Mapping

from .envelopes import bootstrap_envelope
from .idempotency import (
    execute_idempotent,
    normalized_request_hash,
    validate_idempotency_key,
)
from .opening import start_over_session


def execute_start_over(
    *,
    request,
    book_id,
    finalization: Mapping,
    idempotency_key: str | None,
) -> dict:
    """Run and persist one idempotent Reading Session start-over workflow."""
    key = validate_idempotency_key(idempotency_key)
    request_hash = normalized_request_hash(
        method=request.method,
        path=request.path,
        data=finalization,
    )

    def operation():
        session = start_over_session(
            user=request.user,
            book_id=book_id,
            finalization=finalization,
        )
        return bootstrap_envelope(
            request=request,
            book_id=book_id,
            session_id=session.pk,
            created=True,
        )

    return execute_idempotent(
        user=request.user,
        key=key,
        method=request.method,
        path=request.path,
        request_hash=request_hash,
        operation=operation,
    )
