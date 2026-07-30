from __future__ import annotations

from django.db import IntegrityError, transaction
from django.utils import timezone

from library.models import Book

from .models import ReadingSession


def open_session(*, user, book: Book, name: str = "") -> ReadingSession:
    """Return the open Session for a user/Book, creating it only when absent."""
    try:
        with transaction.atomic():
            session, _created = ReadingSession.objects.get_or_create(
                user=user,
                book=book,
                status=ReadingSession.STATUS_ACTIVE,
                defaults={"name": name},
            )
            return session
    except IntegrityError:
        return ReadingSession.objects.get(
            user=user,
            book=book,
            status=ReadingSession.STATUS_ACTIVE,
        )


def close_session(*, session: ReadingSession) -> ReadingSession:
    if not session.is_active:
        return session

    session.status = ReadingSession.STATUS_CLOSED
    session.closed_at = timezone.now()
    session.save(update_fields=["status", "closed_at", "updated_at"])
    return session
