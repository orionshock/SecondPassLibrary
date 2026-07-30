from __future__ import annotations

from django.db.models import Count, DateTimeField, Exists, Max, OuterRef, Prefetch, Q, QuerySet
from django.db.models.functions import Coalesce, Greatest

from library.models import Book, BookAuthor
from library.queries import visible_books_for_user
from marginalia.models import ReadingSession


def marginalia_books_for_user(*, user, q: str = "") -> QuerySet[Book]:
    """Return one annotated Book row per Book with Marginalia owned by ``user``."""
    owned_sessions = Q(marginalia_sessions__user=user)
    queryset = Book.objects.filter(owned_sessions)

    search = (q or "").strip()
    if search:
        queryset = queryset.filter(
            Q(title__icontains=search)
            | Q(book_authors__author__name__icontains=search)
            | Q(book_series__series__name__icontains=search)
        )

    return _marginalia_book_summary_queryset(queryset, user=user)


def marginalia_book_context_for_user(*, user, book_id) -> QuerySet[Book]:
    """Return the canonical Book summary without requiring existing Sessions."""
    return _marginalia_book_summary_queryset(
        Book.objects.filter(pk=book_id),
        user=user,
    )


def _marginalia_book_summary_queryset(
    queryset: QuerySet[Book],
    *,
    user,
) -> QuerySet[Book]:
    owned_sessions = Q(marginalia_sessions__user=user)
    latest_session_activity = Max(
        "marginalia_sessions__updated_at",
        filter=owned_sessions,
    )
    latest_progress_activity = Max(
        "marginalia_sessions__progress_updated_at",
        filter=owned_sessions,
    )
    latest_annotation_activity = Max(
        "marginalia_sessions__annotations__updated_at",
        filter=owned_sessions & Q(marginalia_sessions__annotations__is_deleted=False),
    )
    visible_books = visible_books_for_user(user, cached=False).filter(pk=OuterRef("pk"))

    return (
        queryset.select_related("book_series__series")
        .prefetch_related(
            Prefetch(
                "book_authors",
                queryset=BookAuthor.objects.select_related("author").order_by(
                    "position", "id"
                ),
            )
        )
        .annotate(
            session_count=Count(
                "marginalia_sessions",
                filter=owned_sessions,
                distinct=True,
            ),
            active_session_count=Count(
                "marginalia_sessions",
                filter=owned_sessions
                & Q(marginalia_sessions__status=ReadingSession.STATUS_ACTIVE),
                distinct=True,
            ),
            _latest_session_activity=latest_session_activity,
            _latest_progress_activity=latest_progress_activity,
            _latest_annotation_activity=latest_annotation_activity,
            last_activity_at=Greatest(
                Coalesce(
                    latest_session_activity,
                    latest_progress_activity,
                    output_field=DateTimeField(),
                ),
                Coalesce(
                    latest_progress_activity,
                    latest_session_activity,
                    output_field=DateTimeField(),
                ),
                Coalesce(
                    latest_annotation_activity,
                    latest_session_activity,
                    output_field=DateTimeField(),
                ),
                output_field=DateTimeField(),
            ),
            can_open=Exists(visible_books),
        )
        .order_by("-last_activity_at", "title", "id")
    )
