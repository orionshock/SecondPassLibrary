from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from library.models import Book
from library.queries import visible_books_for_user
from marginalia.exceptions import BookAccessRequiredError, SessionClosedError
from marginalia.models import ReadingSession

from .queries import active_session_for_user_book


class ClosedSessionMutationError(Exception):
    pass


class FinalizationWithoutActiveSessionError(Exception):
    pass


def _locked_owned_session(*, user, session_id) -> ReadingSession:
    return ReadingSession.objects.select_for_update().get(
        pk=session_id,
        user=user,
    )


def _require_book_access(*, user, book_id) -> None:
    if not visible_books_for_user(user, cached=False).filter(pk=book_id).exists():
        raise BookAccessRequiredError


def _locked_accessible_book(*, user, book_id) -> Book:
    book = Book.objects.select_for_update().get(pk=book_id)
    _require_book_access(user=user, book_id=book.pk)
    return book


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
def open_or_create_session(
    *,
    user,
    book_id,
    defaults: Mapping[str, str],
) -> tuple[ReadingSession, bool]:
    book = _locked_accessible_book(user=user, book_id=book_id)
    existing = ReadingSession.objects.select_for_update().filter(
        user=user,
        book=book,
        status=ReadingSession.STATUS_ACTIVE,
    ).first()
    if existing is not None:
        return existing, False

    try:
        with transaction.atomic():
            session = ReadingSession.objects.create(
                user=user,
                book=book,
                name=defaults.get("name", ""),
                notes=defaults.get("notes", ""),
            )
    except IntegrityError:
        session = ReadingSession.objects.get(
            user=user,
            book=book,
            status=ReadingSession.STATUS_ACTIVE,
        )
        return session, False
    return session, True


@transaction.atomic
def start_over_session(
    *,
    user,
    book_id,
    finalization: Mapping,
) -> ReadingSession:
    book = _locked_accessible_book(user=user, book_id=book_id)
    active = ReadingSession.objects.select_for_update().filter(
        user=user,
        book=book,
        status=ReadingSession.STATUS_ACTIVE,
    ).first()
    if active is None:
        if finalization:
            raise FinalizationWithoutActiveSessionError
    else:
        _finalize_for_start_over(session=active, finalization=finalization)

    return ReadingSession.objects.create(user=user, book=book)


def active_session_for_accessible_book(*, user, book_id) -> ReadingSession | None:
    _require_book_access(user=user, book_id=book_id)
    return active_session_for_user_book(user=user, book_id=book_id)


def _finalize_for_start_over(*, session: ReadingSession, finalization: Mapping) -> None:
    closed_at = timezone.now()
    values = {
        "status": ReadingSession.STATUS_CLOSED,
        "closed_at": closed_at,
        "updated_at": closed_at,
    }
    for field in ("name", "notes"):
        if field in finalization:
            values[field] = finalization[field]
    progress = finalization.get("progress")
    if progress is not None:
        values.update(
            progress_cfi=progress["cfi"],
            progress_location_label=progress.get("location_label", ""),
            progress_updated_at=closed_at,
        )
    updated = ReadingSession.objects.filter(
        pk=session.pk,
        status=ReadingSession.STATUS_ACTIVE,
    ).update(**values)
    if not updated:
        raise SessionClosedError


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
