from __future__ import annotations

from collections.abc import Iterable
from typing import Any
from uuid import UUID

from django.db.models import Count, F, Max, Q, QuerySet
from django.db.models.functions import Coalesce, Greatest
from rest_framework.exceptions import NotFound
from rest_framework.exceptions import ValidationError as DRFValidationError

from accounts.roles import is_librarian
from library.models import Book
from library.queries import visible_books_for_user

from ..models import ReadingSession


def _can_view_book(*, user, book: Book) -> bool:
    return visible_books_for_user(user, cached=False).filter(pk=book.pk).exists()


def _book_series_link(book: Book):
    try:
        return book.book_series
    except Book.book_series.RelatedObjectDoesNotExist:
        return None


def _format_series_index(value) -> str | None:
    if value is None:
        return None
    formatted = format(value, "f")
    if "." in formatted:
        formatted = formatted.rstrip("0")
        if formatted.endswith("."):
            formatted += "0"
    return formatted


def get_user_session_queryset(user) -> QuerySet[ReadingSession]:
    return (
        ReadingSession.objects.select_related(
            "book", "book__book_series", "book__book_series__series", "progress"
        )
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
        Book.objects.select_related("book_series", "book_series__series")
        .prefetch_related("authors")
        .filter(id=book_id)
        .first()
    )
    if book is None or not _can_view_book(user=user, book=book):
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
        | Q(book__book_series__series__name__icontains=q)
    )
    visible_book_match = Q()
    if not is_librarian(user):
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


def filtered_session_counts_by_book(queryset: QuerySet[ReadingSession]) -> dict[str, int]:
    rows = (
        queryset.order_by()
        .values("book_id")
        .annotate(filtered_session_count=Count("id", distinct=True))
    )
    return {
        str(row["book_id"]): int(row["filtered_session_count"])
        for row in rows
    }


def build_session_list_context(*, book: Book | None, request=None) -> dict[str, Any]:
    if book is None:
        return {}
    return {"book": book_context_payload(book=book, request=request)}


def book_context_payload(*, book: Book, request=None) -> dict[str, Any]:
    cover_url: str | None = None
    cover = getattr(book, "cover_file", None)
    if cover:
        try:
            url = cover.url
            cover_url = request.build_absolute_uri(url) if request is not None else url
        except Exception:
            cover_url = None

    series_link = _book_series_link(book)
    series = series_link.series if series_link is not None else None
    return {
        "id": str(book.id),
        "title": book.title,
        "authors": list(book.authors.order_by("name").values_list("name", flat=True)),
        "series": (
            {"id": str(series.id), "name": series.name}
            if series is not None
            else None
        ),
        "series_index": (
            _format_series_index(series_link.series_index)
            if series_link is not None
            else None
        ),
        "cover_url": cover_url,
    }


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

        book = getattr(session, "book", None)
        if book is None or not _can_view_book(user=user, book=book):
            continue

        seen_books.add(book_id)
        cover_url: str | None = None
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
        if not _can_view_book(user=user, book=book):
            continue
        visible_books.append(book)

    return reading_activity_summary_for_books(user=user, books=visible_books)


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
        .order_by("-last_activity_at", "-updated_at", "-started_at", "-id")
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
    Product UI helper: list all owned reading sessions for a user.

    Current book visibility controls whether book metadata and open/book links are
    safe to show. It must not hide owned reading history.
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
        ReadingSession.objects.select_related(
            "book", "book__book_series", "book__book_series__series", "progress"
        )
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
        can_open = _can_view_book(user=user, book=book)

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

        if can_open:
            cover_url = ""
            cover = getattr(book, "cover_file", None)
            if cover:
                try:
                    cover_url = str(cover.url)
                except Exception:
                    cover_url = ""

            authors = [a.name for a in book.authors.all()]
            series_link = _book_series_link(book)
            series_name = (
                getattr(series_link.series, "name", "") if series_link is not None else ""
            )
            subtitle = getattr(book, "subtitle", "") or ""
            series_index = (
                _format_series_index(series_link.series_index)
                if series_link is not None
                else None
            )
            title = book.title
        else:
            cover_url = ""
            authors = []
            series_name = ""
            subtitle = ""
            series_index = None
            title = ""

        rows.append(
            {
                "id": str(s.id),
                "name": (s.name or "").strip(),
                "status": s.status,
                "is_active": bool(s.is_active),
                "can_open": bool(can_open),
                "started_at": s.started_at,
                "updated_at": s.updated_at,
                "completed_at": s.completed_at,
                "progression_percent": progression_percent,
                "annotation_count": int(getattr(s, "annotation_count", 0) or 0),
                "last_activity_at": getattr(s, "last_activity_at", None) or s.updated_at,
                "book": {
                    "id": str(book.id),
                    "title": title,
                    "subtitle": subtitle,
                    "authors": authors,
                    "series_name": series_name,
                    "series_index": series_index,
                    "cover_url": cover_url,
                },
            }
        )

    return rows
