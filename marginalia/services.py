from __future__ import annotations

from django.db import IntegrityError, transaction
from django.utils import timezone

from library.models import Book

from .models import ReadingSession


def get_or_create_active_session(*, user, book: Book) -> ReadingSession:
    try:
        with transaction.atomic():
            session, _created = ReadingSession.objects.get_or_create(
                user=user,
                book=book,
                status=ReadingSession.STATUS_ACTIVE,
            )
            return session
    except IntegrityError:
        return ReadingSession.objects.get(
            user=user,
            book=book,
            status=ReadingSession.STATUS_ACTIVE,
        )


def start_new_session(
    *,
    user,
    book: Book,
    name: str = "",
) -> ReadingSession:
    with transaction.atomic():
        ReadingSession.objects.select_for_update().filter(
            user=user,
            book=book,
            status=ReadingSession.STATUS_ACTIVE,
        ).update(status=ReadingSession.STATUS_ARCHIVED)
        return ReadingSession.objects.create(
            user=user,
            book=book,
            name=name,
            status=ReadingSession.STATUS_ACTIVE,
        )


def close_session(*, session: ReadingSession) -> ReadingSession:
    if not session.is_active:
        return session

    session.status = ReadingSession.STATUS_COMPLETED
    session.completed_at = timezone.now()
    session.save(update_fields=["status", "completed_at", "updated_at"])
    return session

