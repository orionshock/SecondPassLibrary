from __future__ import annotations

from django.db import IntegrityError, transaction

from library.models import Book

from .models import Device, ReadingProgress, ReadingSession


def get_or_create_active_session(*, user, book: Book) -> ReadingSession:
    """
    Get the current active session for (user, book), creating one if missing.

    Ensures there is at most one active session per (user, book) even under
    concurrent requests.
    """
    try:
        with transaction.atomic():
            session, _created = ReadingSession.objects.get_or_create(
                user=user,
                book=book,
                is_active=True,
                defaults={"status": ReadingSession.STATUS_ACTIVE},
            )
            return session
    except IntegrityError:
        # Likely concurrent create raced against unique constraint.
        return ReadingSession.objects.get(user=user, book=book, is_active=True)


def start_over_book(*, user, book: Book, name: str | None = None) -> ReadingSession:
    """
    Deactivate the current active session (if any) and create a new active session.

    Preserves old sessions (and their progress/annotations) by archiving them.
    """
    with transaction.atomic():
        (
            ReadingSession.objects.filter(user=user, book=book, is_active=True)
            .select_for_update()
            .update(is_active=False, status=ReadingSession.STATUS_ARCHIVED)
        )
        return ReadingSession.objects.create(
            user=user,
            book=book,
            name=(name or "").strip(),
            status=ReadingSession.STATUS_ACTIVE,
            is_active=True,
        )


def get_or_create_progress(
    *, session: ReadingSession, device: Device | None = None
) -> ReadingProgress:
    """
    Get the ReadingProgress for a session, creating one if missing.
    """
    defaults: dict = {"locator": {}}
    if device is not None:
        defaults["device"] = device
    progress, _created = ReadingProgress.objects.get_or_create(
        session=session, defaults=defaults
    )
    return progress


def update_progress(
    *,
    session: ReadingSession,
    locator: dict,
    progression: float | None = None,
    device: Device | None = None,
) -> ReadingProgress:
    """
    Create or update session progress.

    This function does not perform user-authorization checks; views/serializers are
    expected to enforce user scoping and device/session ownership validation.
    """
    progress = get_or_create_progress(session=session)
    progress.locator = locator
    progress.progression = progression
    progress.device = device
    progress.save(update_fields=["locator", "progression", "device", "updated_at"])
    return progress
