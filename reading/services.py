from __future__ import annotations

from django.db import IntegrityError, transaction
from rest_framework.exceptions import ValidationError

from library.models import Book

from .models import Annotation, Device, ReadingProgress, ReadingSession
from .locators import normalize_current_location
from .profile import CURRENT_READING_PROFILE_VERSION


def is_session_closed(session: ReadingSession) -> bool:
    return (not session.is_active) or (session.status != ReadingSession.STATUS_ACTIVE)


def assert_session_writable(*, session: ReadingSession) -> None:
    if is_session_closed(session):
        raise ValidationError({"detail": "This reading session is closed."})


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
    defaults: dict = {"current_location": {}}
    if device is not None:
        defaults["device"] = device
    progress, _created = ReadingProgress.objects.get_or_create(
        session=session, defaults=defaults
    )
    return progress


def update_progress(
    *,
    session: ReadingSession,
    current_location: dict,
    progression: float | None = None,
    device: Device | None = None,
) -> ReadingProgress:
    """
    Create or update session progress.

    This function does not perform user-authorization checks; views/serializers are
    expected to enforce user scoping and device/session ownership validation.
    """
    assert_session_writable(session=session)
    progress = get_or_create_progress(session=session)
    progress.current_location = normalize_current_location(current_location)
    progress.progression = progression
    progress.device = device
    progress.profile_version = CURRENT_READING_PROFILE_VERSION
    progress.save(
        update_fields=[
            "current_location",
            "progression",
            "device",
            "profile_version",
            "updated_at",
        ]
    )
    return progress


def create_annotation(
    *,
    session: ReadingSession,
    device: Device | None,
    motivation: str,
    target: dict,
    body,
) -> Annotation:
    assert_session_writable(session=session)
    return Annotation.objects.create(
        session=session,
        device=device,
        motivation=motivation,
        target=target,
        body=body,
        # `source_import` is internal/server-managed. Keep it empty for normal creates.
        source_import={},
        profile_version=CURRENT_READING_PROFILE_VERSION,
    )
