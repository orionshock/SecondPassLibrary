from __future__ import annotations

from collections.abc import Mapping

from django.db import transaction
from django.utils import timezone

from library.queries import visible_books_for_user

from .exceptions import BookAccessRequiredError, SessionClosedError
from .models import ReadingSession


def _locked_owned_session(*, user, session_id) -> ReadingSession:
    return ReadingSession.objects.select_for_update().get(
        pk=session_id,
        user=user,
    )


def _require_book_access(*, user, book_id) -> None:
    if not visible_books_for_user(user, cached=False).filter(pk=book_id).exists():
        raise BookAccessRequiredError


@transaction.atomic
def replace_progress(
    *,
    user,
    session_id,
    cfi: str,
    location_label: str,
) -> ReadingSession:
    session = _locked_owned_session(user=user, session_id=session_id)
    if not session.is_active:
        raise SessionClosedError
    _require_book_access(user=user, book_id=session.book_id)

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


@transaction.atomic
def close_owned_session(
    *,
    user,
    session_id,
    metadata: Mapping[str, str],
    progress: Mapping[str, str] | None,
) -> ReadingSession:
    session = _locked_owned_session(user=user, session_id=session_id)
    if not session.is_active:
        if _closed_retry_matches(session=session, metadata=metadata, progress=progress):
            return session
        raise SessionClosedError

    if progress is not None:
        _require_book_access(user=user, book_id=session.book_id)

    closed_at = timezone.now()
    values = {
        "status": ReadingSession.STATUS_CLOSED,
        "closed_at": closed_at,
        "updated_at": closed_at,
        **metadata,
    }

    if progress is not None:
        values.update(
            progress_cfi=progress["cfi"],
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
    return (
        session.progress_cfi == progress["cfi"]
        and session.progress_location_label == progress.get("location_label", "")
    )
