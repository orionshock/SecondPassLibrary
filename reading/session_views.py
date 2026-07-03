from typing import Any, cast

from django.shortcuts import get_object_or_404
from rest_framework import mixins, status, viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.authentication import ClientBearerAuthentication
from core.pagination import DefaultPageNumberPagination
from library import policies as library_policies
from library.models import Book

from .models import Annotation, ReadingSession
from .profile import CURRENT_READING_PROFILE_VERSION
from .session_queries import (
    apply_session_filters,
    build_activity_summary,
    build_session_list_context,
    get_user_session_queryset,
    parse_activity_summary_book_ids,
    parse_recent_sessions_limit,
    recent_sessions_for_user,
    resolve_visible_book_for_session_filter,
)
from .serializers import (
    AnnotationSerializer,
    ReadingProgressSerializer,
    ReadingSessionPatchSerializer,
    ReadingSessionSerializer,
    ReadingSessionSummarySerializer,
)
from .services import (
    assert_session_writable,
    close_session,
    get_or_create_active_session,
    get_or_create_progress,
    start_over_book,
)

def _build_open_response_payload(*, request: Request, session: ReadingSession, view) -> dict[str, Any]:
    progress = get_or_create_progress(session=session)

    annotations_qs = (
        Annotation.objects.select_related("session", "book", "book_file")
        .filter(session=session, is_deleted=False)
        .order_by(*Annotation._meta.ordering)  # type: ignore[arg-type]
    )

    paginator = DefaultPageNumberPagination()
    paginated = paginator.paginate_queryset(annotations_qs, request, view=view)
    annotations_payload = paginator.get_paginated_response(
        AnnotationSerializer(paginated, many=True).data
    ).data

    return {
        "profile_version": CURRENT_READING_PROFILE_VERSION,
        "session": ReadingSessionSerializer(session).data,
        "progress": ReadingProgressSerializer(progress, context={"request": request}).data,
        "annotations": annotations_payload,
    }


class ReadingSessionViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    authentication_classes = [
        SessionAuthentication,
        ClientBearerAuthentication,
    ]
    permission_classes = [IsAuthenticated]

    def _book_filter_from_request(self) -> Book | None:
        request = cast(Request, self.request)
        raw_book = (request.query_params.get("book") or "").strip()
        if not raw_book:
            return None

        if hasattr(self, "_validated_book_filter"):
            return cast(Book | None, getattr(self, "_validated_book_filter"))

        book = resolve_visible_book_for_session_filter(user=request.user, raw_book=raw_book)
        self._validated_book_filter = book
        return book

    def get_queryset(self):
        request = cast(Request, self.request)
        return apply_session_filters(
            get_user_session_queryset(request.user),
            user=request.user,
            book=self._book_filter_from_request(),
            status=request.query_params.get("status") or "",
            is_active=request.query_params.get("is_active") or "",
            q=request.query_params.get("q") or "",
        )

    def list(self, request, *args, **kwargs):
        book_filter = self._book_filter_from_request()
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            if book_filter is not None:
                results = response.data.pop("results")
                response.data["context"] = build_session_list_context(
                    book=book_filter, request=request
                )
                response.data["results"] = results
            return response

        serializer = self.get_serializer(queryset, many=True)
        payload: dict[str, Any] = {"results": serializer.data}
        if book_filter is not None:
            payload["context"] = build_session_list_context(book=book_filter, request=request)
        return Response(payload)

    def get_serializer_class(self):
        if self.action == "partial_update":
            return ReadingSessionPatchSerializer
        return ReadingSessionSummarySerializer

    def create(self, request, *args, **kwargs):
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def update(self, request, *args, **kwargs):
        # Disallow full PUT updates; only PATCH is supported for name/notes.
        if request.method.upper() == "PUT":
            return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        # Session metadata is mutable only while the session is active/writable.
        session = self.get_object()
        assert_session_writable(session=session)
        return super().partial_update(request, *args, **kwargs)


class ActiveSessionView(APIView):
    authentication_classes = [
        SessionAuthentication,
        ClientBearerAuthentication,
    ]
    permission_classes = [IsAuthenticated]

    def get(self, request, book_id):
        book = get_object_or_404(Book, id=book_id)
        if not library_policies.can_view_book(user=request.user, book=book):
            raise NotFound()

        existing = ReadingSession.objects.filter(
            user=request.user, book_id=book_id, is_active=True
        ).first()
        if existing is not None:
            return Response(ReadingSessionSerializer(existing).data)

        session = get_or_create_active_session(user=request.user, book=book)
        return Response(ReadingSessionSerializer(session).data)


class StartOverView(APIView):
    authentication_classes = [
        SessionAuthentication,
        ClientBearerAuthentication,
    ]
    permission_classes = [IsAuthenticated]

    def post(self, request, book_id):
        book = get_object_or_404(Book, id=book_id)
        if not library_policies.can_view_book(user=request.user, book=book):
            raise NotFound()
        name = request.data.get("name", "")
        session = start_over_book(user=request.user, book=book, name=name or "")
        payload = _build_open_response_payload(request=request, session=session, view=self)
        return Response(payload, status=status.HTTP_201_CREATED)


class CloseSessionView(APIView):
    authentication_classes = [
        SessionAuthentication,
        ClientBearerAuthentication,
    ]
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        session = get_object_or_404(ReadingSession, id=session_id, user=request.user)
        session = close_session(session=session)
        return Response(ReadingSessionSerializer(session).data, status=status.HTTP_200_OK)


class RecentSessionsView(APIView):
    authentication_classes = [
        SessionAuthentication,
        ClientBearerAuthentication,
    ]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        limit = parse_recent_sessions_limit(request.query_params.get("limit") or "")
        results = recent_sessions_for_user(user=request.user, request=request, limit=limit)
        return Response({"count": len(results), "results": results}, status=status.HTTP_200_OK)


class ReadingActivitySummaryView(APIView):
    authentication_classes = [
        SessionAuthentication,
        ClientBearerAuthentication,
    ]
    permission_classes = [IsAuthenticated]

    max_books = 100

    def post(self, request):
        raw_books = request.data.get("books") if isinstance(request.data, dict) else None
        ordered_ids = parse_activity_summary_book_ids(raw_books, max_count=self.max_books)

        return Response(
            {"results": build_activity_summary(user=request.user, book_ids=ordered_ids)},
            status=status.HTTP_200_OK,
        )


class OpenBookView(APIView):
    """
    Reader-friendly bootstrap endpoint for opening a book.

    Returns:
    - active session (creating one lazily if missing, subject to current book access)
    - progress (creating if missing)
    - first page of non-deleted annotations for that session
    """

    authentication_classes = [
        SessionAuthentication,
        ClientBearerAuthentication,
    ]
    permission_classes = [IsAuthenticated]

    def post(self, request, book_id):
        created = False

        book = get_object_or_404(Book, id=book_id)
        if not library_policies.can_view_book(user=request.user, book=book):
            raise NotFound()

        session = ReadingSession.objects.select_related("book").filter(
            user=request.user, book_id=book_id, is_active=True
        ).first()

        if session is None:
            session = get_or_create_active_session(user=request.user, book=book)
            created = True

        payload = _build_open_response_payload(request=request, session=session, view=self)

        return Response(
            payload, status=(status.HTTP_201_CREATED if created else status.HTTP_200_OK)
        )


