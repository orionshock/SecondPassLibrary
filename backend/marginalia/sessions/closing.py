from __future__ import annotations

from collections.abc import Mapping

from django.db import transaction
from django.utils import timezone

from marginalia.cfi import validate_durable_cfi
from marginalia.exceptions import SessionClosedError
from marginalia.models import ReadingSession

from .book_access import require_book_access
from .lookup import locked_owned_session


@transaction.atomic
def close_owned_session(
    *,
    user,
    session_id,
    metadata: Mapping[str, str],
    progress: Mapping[str, str] | None,
) -> ReadingSession:
    session = locked_owned_session(user=user, session_id=session_id)
    if not session.is_active:
        if _closed_retry_matches(session=session, metadata=metadata, progress=progress):
            return session
        raise SessionClosedError

    if progress is not None:
        validate_durable_cfi(progress["location"])
        require_book_access(user=user, book_id=session.book_id)

    closed_at = timezone.now()
    values = {
        "status": ReadingSession.STATUS_CLOSED,
        "closed_at": closed_at,
        "updated_at": closed_at,
        **metadata,
    }

    if progress is not None:
        values.update(
            progress_location=progress["location"],
            progress_location_label=progress.get("location_label", ""),
            progress_updated_at=closed_at,
        )

    updated = ReadingSession.objects.filter(
        pk=session.pk,
        user=user,
        status=ReadingSession.STATUS_ACTIVE,
    ).update(**values)
    session.refresh_from_db()
    if not updated:
        if _closed_retry_matches(session=session, metadata=metadata, progress=progress):
            return session
        raise SessionClosedError
    return session


def _closed_retry_matches(
    *,
    session: ReadingSession,
    metadata: Mapping[str, str],
    progress: Mapping[str, str] | None,
) -> bool:
    if any(getattr(session, field) != value for field, value in metadata.items()):
        return False
    if progress is None:
        return True
    return session.progress_location == progress[
        "location"
    ] and session.progress_location_label == progress.get("location_label", "")
