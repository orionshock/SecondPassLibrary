from __future__ import annotations

from collections.abc import Mapping

from django.db import IntegrityError, transaction
from django.utils import timezone

from library.models import Book
from marginalia.cfi import validate_durable_cfi
from marginalia.exceptions import SessionClosedError
from marginalia.models import ReadingSession

from .book_access import require_book_access
from .queries import active_session_for_user_book


class FinalizationWithoutActiveSessionError(Exception):
    pass


def _locked_accessible_book(*, user, book_id) -> Book:
    book = Book.objects.select_for_update().get(pk=book_id)
    require_book_access(user=user, book_id=book.pk)
    return book


@transaction.atomic
def open_or_create_session(
    *,
    user,
    book_id,
    defaults: Mapping[str, str],
) -> tuple[ReadingSession, bool]:
    book = _locked_accessible_book(user=user, book_id=book_id)
    existing = (
        ReadingSession.objects.select_for_update()
        .filter(
            user=user,
            book=book,
            status=ReadingSession.STATUS_ACTIVE,
        )
        .first()
    )
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
    active = (
        ReadingSession.objects.select_for_update()
        .filter(
            user=user,
            book=book,
            status=ReadingSession.STATUS_ACTIVE,
        )
        .first()
    )
    if active is None:
        if finalization:
            raise FinalizationWithoutActiveSessionError
    else:
        _finalize_for_start_over(session=active, finalization=finalization)

    return ReadingSession.objects.create(user=user, book=book)


def active_session_for_accessible_book(*, user, book_id) -> ReadingSession | None:
    require_book_access(user=user, book_id=book_id)
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
        validate_durable_cfi(progress["location"])
        values.update(
            progress_location=progress["location"],
            progress_location_label=progress.get("location_label", ""),
            progress_updated_at=closed_at,
        )
    updated = ReadingSession.objects.filter(
        pk=session.pk,
        status=ReadingSession.STATUS_ACTIVE,
    ).update(**values)
    if not updated:
        raise SessionClosedError
