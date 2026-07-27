from __future__ import annotations

from pathlib import PurePath
import re

from core.operational_logging import user_log_label, user_uuid


_LONG_HEX_RE = re.compile(r"[0-9a-fA-F]{32,}")


def safe_storage_error_message(
    exc: Exception,
    *,
    storage_name: str = "",
    max_length: int = 160,
) -> str:
    """Return a bounded storage error message without paths or storage keys."""
    message = getattr(exc, "strerror", None) or str(exc) or "No error message."
    message = " ".join(str(message).split())
    secrets = {storage_name, PurePath(storage_name).name}
    for secret in secrets:
        if secret:
            message = message.replace(secret, "[redacted]")
    message = " ".join(
        "[redacted]" if "/" in token or "\\" in token else token
        for token in message.split()
    )
    return _LONG_HEX_RE.sub("[redacted]", message)[:max_length]


def log_storage_issue(
    logger,
    *,
    action: str,
    book_id,
    actor=None,
    reason: str,
    exc: Exception | None = None,
    storage_name: str = "",
    operation: str = "",
    reference_state: str = "",
) -> None:
    message = (
        "Storage issue: action=%s book_id=%s actor=%s actor_profile_id=%s "
        "reason=%s error=%s message=%s"
    )
    args = [
        action,
        book_id,
        user_log_label(actor),
        user_uuid(actor),
        reason,
        type(exc).__name__ if exc is not None else "none",
        (
            safe_storage_error_message(exc, storage_name=storage_name)
            if exc is not None
            else "none"
        ),
    ]
    if operation:
        message += " operation=%s"
        args.append(operation)
    if reference_state:
        message += " still_referenced=%s"
        args.append(reference_state)
    logger.warning(message, *args)
