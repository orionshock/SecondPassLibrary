from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction


_STATE_CHANGE_LOGGING_SUPPRESSED: ContextVar[bool] = ContextVar(
    "secondpass_state_change_logging_suppressed",
    default=False,
)


@contextmanager
def suppress_state_change_logging():
    token = _STATE_CHANGE_LOGGING_SUPPRESSED.set(True)
    try:
        yield
    finally:
        _STATE_CHANGE_LOGGING_SUPPRESSED.reset(token)


def state_change_logging_suppressed() -> bool:
    return _STATE_CHANGE_LOGGING_SUPPRESSED.get()


def info_on_commit(logger, message: str, *args) -> None:
    if state_change_logging_suppressed():
        return
    transaction.on_commit(lambda: logger.info(message, *args))


def warning_on_commit(logger, message: str, *args) -> None:
    if state_change_logging_suppressed():
        return
    transaction.on_commit(lambda: logger.warning(message, *args))


def user_uuid(user) -> str:
    if user is None or getattr(user, "is_anonymous", False):
        return "none"
    try:
        return str(user.profile.pk)
    except (AttributeError, ObjectDoesNotExist):
        return "none"


def safe_log_label(value, *, fallback: str, max_length: int = 200) -> str:
    """Return a bounded, single-line label suitable for operational logs."""
    label = " ".join(str(value or "").split())
    if not label:
        label = " ".join(str(fallback or "").split()) or "unknown"
    return label[:max_length]


def user_log_label(user) -> str:
    if user is None or getattr(user, "is_anonymous", False):
        return "none"
    username = user.get_username() if hasattr(user, "get_username") else ""
    return safe_log_label(username, fallback=user_uuid(user))
