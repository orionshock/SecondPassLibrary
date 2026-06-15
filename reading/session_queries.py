from __future__ import annotations

from typing import Any
from uuid import UUID

from django.db.models import Count, F, Max, Q, QuerySet
from django.db.models.functions import Coalesce, Greatest
from rest_framework.exceptions import NotFound
from rest_framework.exceptions import ValidationError as DRFValidationError

from core import policies
from library.models import Book

from .models import ReadingSession
from .services import book_context_payload, reading_activity_summary_for_books


def get_user_session_queryset(user) -> QuerySet[ReadingSession]:
    return (
        ReadingSession.objects.select_related("book", "book__series", "progress")
        .prefetch_related("book__authors")
        .filter(user=user)
        .annotate(
            progression=F("progress__progression"),
            annotation_count=Count(
                "annotations", filter=Q(annotations__is_deleted=False)
            ),
        )
    )


def resolve_visible_book_for_session_filter(*, user, raw_book: str) -> Book | None:
    raw_book = (raw_book or "").strip()
    if not raw_book:
        return None

    try:
        book_id = UUID(raw_book)
    except Exception:
        raise DRFValidationError({"book": "Invalid book id."})

    book = (
        Book.objects.select_related("series")
        .prefetch_related("authors")
        .filter(id=book_id)
        .first()
    )
    if book is None or not policies.can_view_book(user=user, book=book):
        raise NotFound()
    return book


def apply_session_search(
    queryset: QuerySet[ReadingSession], *, user, q: str
) -> QuerySet[ReadingSession]:
    q = (q or "").strip()
    if not q:
        return queryset

    session_match = Q(name__icontains=q) | Q(notes__icontains=q)
    book_match = (
        Q(book__title__icontains=q)
        | Q(book__subtitle__icontains=q)
        | Q(book__authors__name__icontains=q)
        | Q(book__series__name__icontains=q)
    )
    visible_book_match = Q()
    if not policies.can_manage_library(user):
        visible_book_match = Q(book__group_assignments__group__memberships__user=user)
    return queryset.filter(session_match | (visible_book_match & book_match))


def apply_session_filters(
    queryset: QuerySet[ReadingSession],
    *,
    user,
    book: Book | None = None,
    status: str = "",
    is_active: str = "",
    q: str = "",
) -> QuerySet[ReadingSession]:
    if book is not None:
        queryset = queryset.filter(book_id=book.id)

    queryset = apply_session_search(queryset, user=user, q=q)

    raw_status = (status or "").strip()
    if raw_status:
        allowed = {c[0] for c in ReadingSession.STATUS_CHOICES}
        if raw_status not in allowed:
            raise DRFValidationError({"status": "Invalid status."})
        queryset = queryset.filter(status=raw_status)

    raw_is_active = (is_active or "").strip().lower()
    if raw_is_active:
        if raw_is_active in {"1", "true", "t", "yes", "y", "on"}:
            queryset = queryset.filter(is_active=True)
        elif raw_is_active in {"0", "false", "f", "no", "n", "off"}:
            queryset = queryset.filter(is_active=False)
        else:
            raise DRFValidationError({"is_active": "Invalid boolean."})

    return queryset.distinct().order_by("-started_at")


def build_session_list_context(*, book: Book | None, request=None) -> dict[str, Any]:
    if book is None:
        return {}
    return {"book": book_context_payload(book=book, request=request)}


def parse_recent_sessions_limit(raw_limit: str, *, default: int = 10, maximum: int = 50) -> int:
    raw_limit = (raw_limit or "").strip()
    if raw_limit == "":
        return default
    try:
        limit = int(raw_limit)
    except (TypeError, ValueError):
        raise DRFValidationError({"detail": "limit must be an integer."})
    if limit < 1:
        raise DRFValidationError({"detail": "limit must be >= 1."})
    if limit > maximum:
        return maximum
    return limit


def recent_sessions_for_user(*, user, request, limit: int) -> list[dict[str, Any]]:
    ann_updated = Max(
        "annotations__updated_at", filter=Q(annotations__is_deleted=False)
    )
    last_activity = Greatest(
        F("updated_at"),
        Coalesce(F("progress__updated_at"), F("updated_at")),
        Coalesce(ann_updated, F("updated_at")),
    )

    qs = (
        ReadingSession.objects.select_related("book", "progress")
        .filter(
            user=user,
            is_active=True,
            status=ReadingSession.STATUS_ACTIVE,
        )
        .annotate(last_activity_at=last_activity, latest_annotation_updated_at=ann_updated)
        .order_by("-last_activity_at", "-updated_at", "-started_at")
    )

    seen_books: set[str] = set()
    results: list[dict[str, Any]] = []
    for session in qs[: max(50, limit * 5)]:
        book_id = str(getattr(session, "book_id", ""))
        if not book_id or book_id in seen_books:
            continue
        seen_books.add(book_id)

        book = getattr(session, "book", None)
        cover_url: str | None = None
        if book is not None:
            cover = getattr(book, "cover_file", None)
            if cover:
                try:
                    cover_url = request.build_absolute_uri(cover.url)
                except Exception:
                    cover_url = None

        results.append(
            {
                "last_activity_at": getattr(session, "last_activity_at", None)
                or session.updated_at,
                "session": {
                    "id": str(session.id),
                    "name": (getattr(session, "name", "") or "").strip(),
                    "status": session.status,
                    "is_active": bool(session.is_active),
                    "progression": (
                        getattr(getattr(session, "progress", None), "progression", None)
                    ),
                },
                "book": {
                    "id": book_id,
                    "title": getattr(book, "title", "") if book is not None else "",
                    "cover_url": cover_url,
                },
            }
        )
        if len(results) >= limit:
            break

    return results


def parse_activity_summary_book_ids(raw_books, *, max_count: int = 100) -> list[UUID]:
    if raw_books is None:
        raise DRFValidationError({"books": "This field is required."})
    if not isinstance(raw_books, list):
        raise DRFValidationError({"books": "Must be a list of book ids."})
    if len(raw_books) > max_count:
        raise DRFValidationError({"books": f"Maximum {max_count} book ids."})

    ordered_ids: list[UUID] = []
    seen: set[str] = set()
    for raw in raw_books:
        try:
            book_id = UUID(str(raw))
        except Exception:
            raise DRFValidationError({"books": "Invalid book id."})
        key = str(book_id)
        if key in seen:
            continue
        seen.add(key)
        ordered_ids.append(book_id)
    return ordered_ids


def build_activity_summary(*, user, book_ids: list[UUID]) -> list[dict[str, Any]]:
    if not book_ids:
        return []

    books_by_id = {
        book.id: book
        for book in Book.objects.filter(id__in=book_ids).prefetch_related(
            "group_assignments"
        )
    }
    visible_books: list[Book] = []
    for book_id in book_ids:
        book = books_by_id.get(book_id)
        if book is None:
            continue
        if not policies.can_view_book(user=user, book=book):
            continue
        visible_books.append(book)

    return reading_activity_summary_for_books(user=user, books=visible_books)
