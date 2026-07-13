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
