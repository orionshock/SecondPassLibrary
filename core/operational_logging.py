from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar

from django.core.exceptions import ObjectDoesNotExist


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


def user_uuid(user) -> str:
    if user is None or getattr(user, "is_anonymous", False):
        return "none"
    try:
        return str(user.profile.pk)
    except (AttributeError, ObjectDoesNotExist):
        return "none"
