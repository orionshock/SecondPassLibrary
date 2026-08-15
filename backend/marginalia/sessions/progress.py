from __future__ import annotations

from datetime import datetime

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from marginalia.exceptions import SessionClosedError
from marginalia.models import ReadingSession

from .book_access import require_book_access
from .lookup import locked_owned_session


@transaction.atomic
def assign_session_progress(
    *,
    session: ReadingSession,
    cfi: str,
    location_label: str = "",
    updated_at: datetime | None = None,
) -> ReadingSession:
    if not cfi:
        raise ValidationError({"cfi": "Saved progress requires a CFI."})
    _update_active_session(
        session=session,
        progress_cfi=cfi,
        progress_location_label=location_label,
        progress_updated_at=updated_at or timezone.now(),
    )
    return session


@transaction.atomic
def clear_session_progress(*, session: ReadingSession) -> ReadingSession:
    _update_active_session(
        session=session,
        progress_cfi="",
        progress_location_label="",
        progress_updated_at=None,
    )
    return session


def _update_active_session(*, session: ReadingSession, **values) -> None:
    updated = ReadingSession.objects.filter(
        pk=session.pk,
        status=ReadingSession.STATUS_ACTIVE,
    ).update(**values)
    if not updated:
        raise ValidationError("Closed Sessions cannot update progress.")
    for field, value in values.items():
        setattr(session, field, value)


@transaction.atomic
def replace_progress(
    *,
    user,
    session_id,
    cfi: str,
    location_label: str,
) -> ReadingSession:
    session = locked_owned_session(user=user, session_id=session_id)
    if not session.is_active:
        raise SessionClosedError
    require_book_access(user=user, book_id=session.book_id)

    updated_at = timezone.now()
    updated = ReadingSession.objects.filter(
        pk=session.pk,
        user=user,
        status=ReadingSession.STATUS_ACTIVE,
    ).update(
        progress_cfi=cfi,
        progress_location_label=location_label,
        progress_updated_at=updated_at,
    )
    if not updated:
        raise SessionClosedError
    session.progress_cfi = cfi
    session.progress_location_label = location_label
    session.progress_updated_at = updated_at
    return session
