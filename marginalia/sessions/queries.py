from __future__ import annotations

from django.db.models import Count, DateTimeField, Exists, Max, OuterRef, Q, QuerySet
from django.db.models.functions import Coalesce, Greatest
from rest_framework.exceptions import ValidationError

from library.models import Book
from library.queries import visible_books_for_user
from marginalia.models import ReadingSession


def marginalia_sessions_for_book(
    *,
    user,
    book: Book,
    status: str = "",
    q: str = "",
) -> QuerySet[ReadingSession]:
    queryset = ReadingSession.objects.filter(user=user, book=book)
    search = (q or "").strip()
    if search:
        queryset = queryset.filter(Q(name__icontains=search) | Q(notes__icontains=search))
    queryset = _filter_session_status(queryset, status=status)
    return _session_summary_queryset(queryset, user=user)


def marginalia_sessions_for_user(
    *,
    user,
    status: str = "",
    q: str = "",
) -> QuerySet[ReadingSession]:
    queryset = ReadingSession.objects.filter(user=user)
    search = (q or "").strip()
    if search:
        queryset = queryset.filter(
            Q(name__icontains=search)
            | Q(notes__icontains=search)
            | Q(book__title__icontains=search)
            | Q(book__book_authors__author__name__icontains=search)
            | Q(book__book_series__series__name__icontains=search)
        )
    queryset = _filter_session_status(queryset, status=status)
    return _session_summary_queryset(queryset, user=user)


def recent_marginalia_sessions_for_user(
    *,
    user,
    include_closed: bool = False,
    limit: int = 10,
) -> QuerySet[ReadingSession]:
    """Return the bounded, server-ordered Dashboard Session collection."""
    queryset = ReadingSession.objects.filter(user=user)
    if not include_closed:
        queryset = queryset.filter(status=ReadingSession.STATUS_ACTIVE)
    return _session_summary_queryset(queryset, user=user)[:limit]


def marginalia_session_for_user(*, user, session_id) -> QuerySet[ReadingSession]:
    return _session_summary_queryset(
        ReadingSession.objects.filter(user=user, pk=session_id),
        user=user,
    )


def active_session_for_user_book(*, user, book_id) -> ReadingSession | None:
    return ReadingSession.objects.filter(
        user=user,
        book_id=book_id,
        status=ReadingSession.STATUS_ACTIVE,
    ).first()


def _filter_session_status(
    queryset: QuerySet[ReadingSession],
    *,
    status: str,
) -> QuerySet[ReadingSession]:
    raw_status = (status or "").strip()
    allowed_statuses = {choice[0] for choice in ReadingSession.STATUS_CHOICES}
    if raw_status and raw_status not in allowed_statuses:
        raise ValidationError({"status": "Invalid status."})
    if raw_status:
        queryset = queryset.filter(status=raw_status)
    return queryset


def _session_summary_queryset(
    queryset: QuerySet[ReadingSession],
    *,
    user,
) -> QuerySet[ReadingSession]:
    latest_annotation_activity = Max(
        "annotations__updated_at",
        filter=Q(annotations__is_deleted=False),
    )
    visible_books = visible_books_for_user(user, cached=False).filter(
        pk=OuterRef("book_id")
    )
    return (
        queryset.select_related("book")
        .annotate(
            annotation_count=Count(
                "annotations",
                filter=Q(annotations__is_deleted=False),
                distinct=True,
            ),
            last_activity_at=Greatest(
                "updated_at",
                Coalesce("progress_updated_at", "updated_at"),
                Coalesce(latest_annotation_activity, "updated_at"),
                output_field=DateTimeField(),
            ),
            can_open=Exists(visible_books),
        )
        .order_by("-last_activity_at", "-started_at", "-id")
    )
