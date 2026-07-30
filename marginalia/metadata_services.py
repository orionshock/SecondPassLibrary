from __future__ import annotations

from collections.abc import Mapping

from django.db import transaction

from .models import ReadingSession


class ClosedSessionMutationError(Exception):
    pass


@transaction.atomic
def update_session_metadata(
    *,
    session: ReadingSession,
    changes: Mapping[str, str],
) -> ReadingSession:
    unsupported = set(changes) - {"name", "notes"}
    if unsupported:
        raise ValueError("Session metadata changes may contain only name and notes.")

    locked = ReadingSession.objects.select_for_update().get(pk=session.pk)
    if not locked.is_active:
        raise ClosedSessionMutationError
    if not changes:
        return locked

    for field, value in changes.items():
        setattr(locked, field, value)
    locked.save(update_fields=[*changes, "updated_at"])
    return locked
