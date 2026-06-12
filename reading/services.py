from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from library.models import Book
from core import policies

from .models import Annotation, ReadingProgress, ReadingSession
from .models import HIGHLIGHT_COLOR_YELLOW
from .locators import normalize_current_location
from .profile import CURRENT_READING_PROFILE_VERSION
from django.db.models import Count, Max, Q, F
from django.db.models.functions import Coalesce, Greatest


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


def book_context_payload(*, book: Book, request=None) -> dict[str, Any]:
    cover_url: str | None = None
    cover = getattr(book, "cover_file", None)
    if cover:
        try:
            url = cover.url
            cover_url = request.build_absolute_uri(url) if request is not None else url
        except Exception:
            cover_url = None

    series = getattr(book, "series", None)
    return {
        "id": str(book.id),
        "title": book.title,
        "authors": list(book.authors.order_by("name").values_list("name", flat=True)),
        "series": (
            {"id": str(series.id), "name": series.name}
            if series is not None
            else None
        ),
        "series_index": str(book.series_index) if book.series_index is not None else None,
        "cover_url": cover_url,
    }


def reading_activity_summary_for_books(
    *, user, books: Iterable[Book]
) -> list[dict[str, Any]]:
    books_by_id = {str(book.id): book for book in books}
    ordered_book_ids = list(books_by_id.keys())
    if not ordered_book_ids:
        return []

    counts_by_book = {
        str(row["book_id"]): row
        for row in (
            ReadingSession.objects.filter(user=user, book_id__in=ordered_book_ids)
            .values("book_id")
            .annotate(
                session_count=Count("id"),
                active_session_count=Count(
                    "id",
                    filter=Q(
                        is_active=True,
                        status=ReadingSession.STATUS_ACTIVE,
                    ),
                ),
            )
        )
    }

    latest_by_book: dict[str, ReadingSession] = {}
    for session in (
        ReadingSession.objects.filter(user=user, book_id__in=ordered_book_ids)
        .only("id", "book_id", "updated_at", "started_at")
        .order_by("book_id", "-updated_at", "-started_at", "-id")
    ):
        latest_by_book.setdefault(str(session.book_id), session)

    active_by_book: dict[str, ReadingSession] = {}
    for session in (
        ReadingSession.objects.filter(
            user=user,
            book_id__in=ordered_book_ids,
            is_active=True,
            status=ReadingSession.STATUS_ACTIVE,
        )
        .only("id", "book_id", "updated_at", "started_at")
        .order_by("book_id", "-updated_at", "-started_at", "-id")
    ):
        active_by_book.setdefault(str(session.book_id), session)

    results: list[dict[str, Any]] = []
    for book_id in ordered_book_ids:
        count_row = counts_by_book.get(book_id, {})
        active = active_by_book.get(book_id)
        latest = latest_by_book.get(book_id)
        results.append(
            {
                "book": book_id,
                "session_count": int(count_row.get("session_count") or 0),
                "active_session_count": int(count_row.get("active_session_count") or 0),
                "active_session_id": str(active.id) if active is not None else None,
                "latest_session_id": str(latest.id) if latest is not None else None,
                "latest_session_updated_at": (
                    latest.updated_at if latest is not None else None
                ),
            }
        )
    return results


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
    anchor_kind: str,
    selector_kind: str,
    selector_value: str,
    highlight_text: str = "",
    quote_prefix: str = "",
    quote_suffix: str = "",
    highlight_color: str = "",
    comment_text: str = "",
) -> Annotation:
    assert_session_writable(session=session)
    book = session.book
    book_file = getattr(book, "file", None)

    if (highlight_text or highlight_color) and not highlight_color:
        highlight_color = HIGHLIGHT_COLOR_YELLOW

    motivation = (
        Annotation.MOTIVATION_BOOKMARKING
        if anchor_kind == Annotation.ANCHOR_KIND_BOOKMARK
        else Annotation.MOTIVATION_HIGHLIGHTING
    )

    return Annotation.objects.create(
        session=session,
        book=book,
        book_file=book_file,
        motivation=motivation,
        anchor_kind=anchor_kind,
        selector_kind=selector_kind,
        selector_value=selector_value,
        highlight_text=highlight_text or "",
        quote_prefix=quote_prefix or "",
        quote_suffix=quote_suffix or "",
        highlight_color=highlight_color or "",
        comment_text=comment_text or "",
        profile_version=CURRENT_READING_PROFILE_VERSION,
    )


def update_annotation(
    *,
    annotation: Annotation,
    anchor_kind: str,
    selector_kind: str,
    selector_value: str,
    highlight_text: str = "",
    quote_prefix: str = "",
    quote_suffix: str = "",
    highlight_color: str = "",
    comment_text: str = "",
) -> Annotation:
    assert_session_writable(session=annotation.session)
    motivation = (
        Annotation.MOTIVATION_BOOKMARKING
        if anchor_kind == Annotation.ANCHOR_KIND_BOOKMARK
        else Annotation.MOTIVATION_HIGHLIGHTING
    )
    annotation.motivation = motivation
    annotation.anchor_kind = anchor_kind
    annotation.selector_kind = selector_kind
    annotation.selector_value = selector_value
    annotation.highlight_text = highlight_text or ""
    annotation.quote_prefix = quote_prefix or ""
    annotation.quote_suffix = quote_suffix or ""
    if (annotation.highlight_text or highlight_color) and not highlight_color:
        highlight_color = HIGHLIGHT_COLOR_YELLOW
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
            "anchor_kind",
            "selector_kind",
            "selector_value",
            "highlight_text",
            "quote_prefix",
            "quote_suffix",
            "highlight_color",
            "comment_text",
            "profile_version",
            "book",
            "book_file",
            "updated_at",
        ]
    )
    return annotation


def update_annotation_content(
    *,
    annotation: Annotation,
    comment_text: str | None = None,
    highlight_color: str | None = None,
) -> Annotation:
    """
    Update the user-editable content of an annotation without changing its anchor.

    Allowed updates:
    - comment_text (note/comment body)
    - highlight_color (highlight token)
    """
    assert_session_writable(session=annotation.session)

    update_fields: list[str] = []
    if comment_text is not None:
        if annotation.anchor_kind != Annotation.ANCHOR_KIND_HIGHLIGHT:
            raise ValidationError("Comments are only supported on highlights.")
        annotation.comment_text = comment_text or ""
        update_fields.append("comment_text")
    if highlight_color is not None:
        if annotation.anchor_kind != Annotation.ANCHOR_KIND_HIGHLIGHT:
            raise ValidationError("Highlight color applies only to highlights.")
        annotation.highlight_color = highlight_color or ""
        update_fields.append("highlight_color")

    if update_fields:
        update_fields.extend(["updated_at"])
        annotation.save(update_fields=update_fields)
    return annotation


def list_sessions_for_book(*, user, book: Book) -> list[dict]:
    """
    Product UI helper: list all reading sessions for a user+book with lightweight
    progress/activity summary.

    This is intentionally session-auth/UI scoped and should not broaden bearer-token
    surfaces by itself.
    """
    ann_updated = Max(
        "annotations__updated_at", filter=Q(annotations__is_deleted=False)
    )
    last_activity = Greatest(
        F("updated_at"),
        Coalesce(F("progress__updated_at"), F("updated_at")),
        Coalesce(ann_updated, F("updated_at")),
    )

    qs = (
        ReadingSession.objects.select_related("progress")
        .filter(user=user, book=book)
        .annotate(
            last_activity_at=last_activity,
            annotation_count=Count("annotations", filter=Q(annotations__is_deleted=False)),
        )
        .order_by("-last_activity_at", "-updated_at", "-started_at")
    )

    rows: list[dict] = []
    for s in qs:
        progress = getattr(s, "progress", None)
        progression = getattr(progress, "progression", None) if progress is not None else None
        progression_percent: float | None = None
        if progression is not None:
            try:
                progression_percent = float(progression) * 100.0
            except (TypeError, ValueError):
                progression_percent = None
        rows.append(
            {
                "id": str(s.id),
                "name": (s.name or "").strip(),
                "status": s.status,
                "is_active": bool(s.is_active),
                "started_at": s.started_at,
                "updated_at": s.updated_at,
                "completed_at": s.completed_at,
                "progression": progression,
                "progression_percent": progression_percent,
                "annotation_count": int(getattr(s, "annotation_count", 0) or 0),
                "last_activity_at": getattr(s, "last_activity_at", None) or s.updated_at,
            }
        )
    return rows


def list_sessions_for_user(*, user) -> list[dict]:
    """
    Product UI helper: list all reading sessions for a user across visible books.

    Visibility is evaluated using `policies.can_view_book()`.
    """
    ann_updated = Max(
        "annotations__updated_at", filter=Q(annotations__is_deleted=False)
    )
    last_activity = Greatest(
        F("updated_at"),
        Coalesce(F("progress__updated_at"), F("updated_at")),
        Coalesce(ann_updated, F("updated_at")),
    )

    qs = (
        ReadingSession.objects.select_related("book", "book__series", "progress")
        .prefetch_related("book__authors")
        .filter(user=user)
        .annotate(
            last_activity_at=last_activity,
            annotation_count=Count("annotations", filter=Q(annotations__is_deleted=False)),
        )
        .order_by("-last_activity_at", "-updated_at", "-started_at")
    )

    rows: list[dict] = []
    for s in qs:
        book = getattr(s, "book", None)
        if book is None:
            continue
        if not policies.can_view_book(user=user, book=book):
            continue

        progress = getattr(s, "progress", None)
        progression = (
            getattr(progress, "progression", None) if progress is not None else None
        )
        progression_percent: float | None = None
        if progression is not None:
            try:
                progression_percent = float(progression) * 100.0
            except (TypeError, ValueError):
                progression_percent = None

        cover_url = ""
        cover = getattr(book, "cover_file", None)
        if cover:
            try:
                cover_url = str(cover.url)
            except Exception:
                cover_url = ""

        authors = [a.name for a in book.authors.all()]
        series_name = getattr(getattr(book, "series", None), "name", "") or ""

        rows.append(
            {
                "id": str(s.id),
                "name": (s.name or "").strip(),
                "status": s.status,
                "is_active": bool(s.is_active),
                "started_at": s.started_at,
                "updated_at": s.updated_at,
                "completed_at": s.completed_at,
                "progression_percent": progression_percent,
                "annotation_count": int(getattr(s, "annotation_count", 0) or 0),
                "last_activity_at": getattr(s, "last_activity_at", None) or s.updated_at,
                "book": {
                    "id": str(book.id),
                    "title": book.title,
                    "subtitle": getattr(book, "subtitle", "") or "",
                    "authors": authors,
                    "series_name": series_name,
                    "series_index": getattr(book, "series_index", None),
                    "cover_url": cover_url,
                },
            }
        )

    return rows
