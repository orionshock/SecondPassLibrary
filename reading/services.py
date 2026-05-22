from __future__ import annotations

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from library.models import Book

from .models import Annotation, ReadingProgress, ReadingSession
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


def close_session(*, session: ReadingSession) -> ReadingSession:
    """
    Mark a reading session as completed/closed.

    Idempotent:
    - If the session is already closed, no changes are made (completed_at is preserved).
    - If the session is active, it becomes completed/inactive and completed_at is set.
    """
    if is_session_closed(session):
        return session

    now = timezone.now()
    session.is_active = False
    session.status = ReadingSession.STATUS_COMPLETED
    if session.completed_at is None:
        session.completed_at = now
    session.save(update_fields=["is_active", "status", "completed_at", "updated_at"])
    return session


def get_or_create_progress(*, session: ReadingSession) -> ReadingProgress:
    """
    Get the ReadingProgress for a session, creating one if missing.
    """
    progress, _created = ReadingProgress.objects.get_or_create(
        session=session, defaults={"current_location": {}}
    )
    return progress


def update_progress(
    *,
    session: ReadingSession,
    current_location: dict,
    progression: float | None = None,
) -> ReadingProgress:
    """
    Create or update session progress.

    This function does not perform user-authorization checks; views/serializers are
    expected to enforce user scoping and session ownership validation.
    """
    assert_session_writable(session=session)
    progress = get_or_create_progress(session=session)
    progress.current_location = normalize_current_location(current_location)
    progress.progression = progression
    progress.profile_version = CURRENT_READING_PROFILE_VERSION
    progress.save(
        update_fields=[
            "current_location",
            "progression",
            "profile_version",
            "updated_at",
        ]
    )
    return progress


def create_annotation(
    *,
    session: ReadingSession,
    motivation: str,
    selector_kind: str,
    selector_value: str,
    highlight_text: str = "",
    highlight_color: str = "",
    comment_text: str = "",
) -> Annotation:
    assert_session_writable(session=session)
    book = session.book
    book_file = getattr(book, "file", None)
    return Annotation.objects.create(
        session=session,
        book=book,
        book_file=book_file,
        motivation=motivation,
        selector_kind=selector_kind,
        selector_value=selector_value,
        highlight_text=highlight_text or "",
        highlight_color=highlight_color or "",
        comment_text=comment_text or "",
        # `source_import` is internal/server-managed. Keep it empty for normal creates.
        source_import={},
        profile_version=CURRENT_READING_PROFILE_VERSION,
    )


def update_annotation(
    *,
    annotation: Annotation,
    motivation: str,
    selector_kind: str,
    selector_value: str,
    highlight_text: str = "",
    highlight_color: str = "",
    comment_text: str = "",
) -> Annotation:
    assert_session_writable(session=annotation.session)
    annotation.motivation = motivation
    annotation.selector_kind = selector_kind
    annotation.selector_value = selector_value
    annotation.highlight_text = highlight_text or ""
    annotation.highlight_color = highlight_color or ""
    annotation.comment_text = comment_text or ""
    annotation.profile_version = CURRENT_READING_PROFILE_VERSION

    # Keep book/book_file consistent with the session's book at write time.
    book = annotation.session.book
    annotation.book = book
    annotation.book_file = getattr(book, "file", None)

    annotation.save(
        update_fields=[
            "motivation",
            "selector_kind",
            "selector_value",
            "highlight_text",
            "highlight_color",
            "comment_text",
            "profile_version",
            "book",
            "book_file",
            "updated_at",
        ]
    )
    return annotation
