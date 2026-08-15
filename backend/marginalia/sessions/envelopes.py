from __future__ import annotations

from urllib.parse import urlencode

from django.shortcuts import get_object_or_404
from django.urls import reverse

from core.pagination import DefaultPageNumberPagination
from marginalia.annotations.collection import annotation_collection
from marginalia.books.queries import (
    marginalia_book_context_for_user,
    marginalia_books_for_user,
)
from marginalia.books.serializers import MarginaliaBookSummarySerializer
from marginalia.models import ReadingSession

from .queries import marginalia_session_for_user, marginalia_sessions_for_book
from .serializers import (
    MarginaliaSessionDetailEnvelopeSerializer,
    MarginaliaSessionDetailSerializer,
    MarginaliaSessionSummarySerializer,
)


def session_detail_envelope(*, request, session_id) -> dict:
    session = get_object_or_404(
        marginalia_session_for_user(user=request.user, session_id=session_id)
    )
    book = get_object_or_404(
        marginalia_books_for_user(user=request.user),
        pk=session.book_id,
    )
    return MarginaliaSessionDetailEnvelopeSerializer(
        {"context": {"book": book}, "session": session},
        context={"request": request},
    ).data


def bootstrap_envelope(*, request, book_id, session_id=None, created: bool) -> dict:
    book = marginalia_book_context_for_user(
        user=request.user,
        book_id=book_id,
    ).get()
    session = None
    annotations = []
    if session_id is not None:
        session = marginalia_session_for_user(
            user=request.user,
            session_id=session_id,
        ).get()
        annotations = annotation_collection(session)["annotations"]

    closed_queryset = marginalia_sessions_for_book(
        user=request.user,
        book=book,
        status=ReadingSession.STATUS_CLOSED,
    )
    page_size = DefaultPageNumberPagination.page_size
    closed_count = closed_queryset.count()
    closed_sessions = list(closed_queryset[:page_size])

    return {
        "created": created,
        "context": {
            "book": MarginaliaBookSummarySerializer(
                book,
                context={"request": request},
            ).data
        },
        "session": (
            MarginaliaSessionDetailSerializer(session).data
            if session is not None
            else None
        ),
        "annotations": annotations,
        "closed_sessions": {
            "count": closed_count,
            "next": _closed_page_url(request=request, book_id=book_id, page=2)
            if closed_count > page_size
            else None,
            "previous": None,
            "results": MarginaliaSessionSummarySerializer(
                closed_sessions,
                many=True,
            ).data,
        },
    }


def _closed_page_url(*, request, book_id, page: int) -> str:
    path = reverse("marginalia:book-session-list", kwargs={"book_id": book_id})
    query = urlencode({"status": ReadingSession.STATUS_CLOSED, "page": page})
    return request.build_absolute_uri(f"{path}?{query}")
