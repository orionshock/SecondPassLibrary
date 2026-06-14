from typing import Any, cast
from uuid import UUID

from django.db.models import Count, F, Max, Q
from django.db.models.functions import Coalesce, Greatest
from django.shortcuts import get_object_or_404
from rest_framework import mixins, status, viewsets
from rest_framework.authentication import BasicAuthentication, SessionAuthentication
from rest_framework.exceptions import NotFound
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.authentication import ClientBearerAuthentication
from core import policies
from core.pagination import DefaultPageNumberPagination
from library.models import Book

from .models import Annotation, ReadingSession
from .profile import CURRENT_READING_PROFILE_VERSION
from .serializers import (
    AnnotationSerializer,
    ReadingProgressSerializer,
    ReadingSessionPatchSerializer,
    ReadingSessionSerializer,
    ReadingSessionSummarySerializer,
)
from .services import (
    assert_session_writable,
    book_context_payload,
    close_session,
    get_or_create_active_session,
    get_or_create_progress,
    reading_activity_summary_for_books,
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
        BasicAuthentication,
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
        if book is None or not policies.can_view_book(user=request.user, book=book):
            raise NotFound()

        self._validated_book_filter = book
        return book

    def get_queryset(self):
        request = cast(Request, self.request)
        qs = (
            ReadingSession.objects.select_related("book", "book__series", "progress")
            .prefetch_related("book__authors")
            .filter(user=request.user)
            .annotate(
                progression=F("progress__progression"),
                annotation_count=Count(
                    "annotations", filter=Q(annotations__is_deleted=False)
                ),
            )
        )

        book_filter = self._book_filter_from_request()
        if book_filter is not None:
            qs = qs.filter(book_id=book_filter.id)

        q = (request.query_params.get("q") or "").strip()
        if q:
            session_match = Q(name__icontains=q) | Q(notes__icontains=q)
            book_match = (
                Q(book__title__icontains=q)
                | Q(book__subtitle__icontains=q)
                | Q(book__authors__name__icontains=q)
                | Q(book__series__name__icontains=q)
            )
            visible_book_match = Q()
            if not policies.can_manage_library(request.user):
                visible_book_match = Q(
                    book__group_assignments__group__memberships__user=request.user
                )
            qs = qs.filter(session_match | (visible_book_match & book_match))

        raw_status = (request.query_params.get("status") or "").strip()
        if raw_status:
            allowed = {c[0] for c in ReadingSession.STATUS_CHOICES}
            if raw_status not in allowed:
                raise DRFValidationError({"status": "Invalid status."})
            qs = qs.filter(status=raw_status)

        raw_is_active = (request.query_params.get("is_active") or "").strip().lower()
        if raw_is_active:
            if raw_is_active in {"1", "true", "t", "yes", "y", "on"}:
                qs = qs.filter(is_active=True)
            elif raw_is_active in {"0", "false", "f", "no", "n", "off"}:
                qs = qs.filter(is_active=False)
            else:
                raise DRFValidationError({"is_active": "Invalid boolean."})

        return qs.distinct().order_by("-started_at")

    def list(self, request, *args, **kwargs):
        book_filter = self._book_filter_from_request()
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            if book_filter is not None:
                results = response.data.pop("results")
                response.data["context"] = {
                    "book": book_context_payload(book=book_filter, request=request)
                }
                response.data["results"] = results
            return response

        serializer = self.get_serializer(queryset, many=True)
        payload: dict[str, Any] = {"results": serializer.data}
        if book_filter is not None:
            payload["context"] = {
                "book": book_context_payload(book=book_filter, request=request)
            }
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
        BasicAuthentication,
        ClientBearerAuthentication,
    ]
    permission_classes = [IsAuthenticated]

    def get(self, request, book_id):
        # If the user already has an active session for this book, return it even
        # if they no longer have current library access (user-owned reading data).
        existing = ReadingSession.objects.filter(
            user=request.user, book_id=book_id, is_active=True
        ).first()
        if existing is not None:
            return Response(ReadingSessionSerializer(existing).data)

        book = get_object_or_404(Book, id=book_id)
        if not policies.can_view_book(user=request.user, book=book):
            raise NotFound()
        session = get_or_create_active_session(user=request.user, book=book)
        return Response(ReadingSessionSerializer(session).data)


class StartOverView(APIView):
    authentication_classes = [
        SessionAuthentication,
        BasicAuthentication,
        ClientBearerAuthentication,
    ]
    permission_classes = [IsAuthenticated]

    def post(self, request, book_id):
        book = get_object_or_404(Book, id=book_id)
        if not policies.can_view_book(user=request.user, book=book):
            raise NotFound()
        name = request.data.get("name", "")
        session = start_over_book(user=request.user, book=book, name=name or "")
        payload = _build_open_response_payload(request=request, session=session, view=self)
        return Response(payload, status=status.HTTP_201_CREATED)


class CloseSessionView(APIView):
    authentication_classes = [
        SessionAuthentication,
        BasicAuthentication,
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
        BasicAuthentication,
        ClientBearerAuthentication,
    ]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        raw_limit = (request.query_params.get("limit") or "").strip()
        if raw_limit == "":
            limit = 10
        else:
            try:
                limit = int(raw_limit)
            except (TypeError, ValueError):
                raise DRFValidationError({"detail": "limit must be an integer."})
            if limit < 1:
                raise DRFValidationError({"detail": "limit must be >= 1."})
            if limit > 50:
                limit = 50

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
                user=request.user,
                is_active=True,
                status=ReadingSession.STATUS_ACTIVE,
            )
            .annotate(last_activity_at=last_activity, latest_annotation_updated_at=ann_updated)
            .order_by("-last_activity_at", "-updated_at", "-started_at")
        )

        # Defensive dedupe by book (should already be unique for active sessions).
        seen_books: set[str] = set()
        results: list[dict[str, Any]] = []
        for s in qs[: max(50, limit * 5)]:
            book_id = str(getattr(s, "book_id", ""))
            if not book_id or book_id in seen_books:
                continue
            seen_books.add(book_id)

            book = getattr(s, "book", None)
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
                    "last_activity_at": getattr(s, "last_activity_at", None) or s.updated_at,
                    "session": {
                        "id": str(s.id),
                        "name": (getattr(s, "name", "") or "").strip(),
                        "status": s.status,
                        "is_active": bool(s.is_active),
                        "progression": (
                            getattr(getattr(s, "progress", None), "progression", None)
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

        return Response({"count": len(results), "results": results}, status=status.HTTP_200_OK)


class ReadingActivitySummaryView(APIView):
    authentication_classes = [
        SessionAuthentication,
        BasicAuthentication,
        ClientBearerAuthentication,
    ]
    permission_classes = [IsAuthenticated]

    max_books = 100

    def post(self, request):
        raw_books = request.data.get("books") if isinstance(request.data, dict) else None
        if raw_books is None:
            raise DRFValidationError({"books": "This field is required."})
        if not isinstance(raw_books, list):
            raise DRFValidationError({"books": "Must be a list of book ids."})
        if len(raw_books) > self.max_books:
            raise DRFValidationError({"books": f"Maximum {self.max_books} book ids."})

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

        if not ordered_ids:
            return Response({"results": []}, status=status.HTTP_200_OK)

        books_by_id = {
            book.id: book
            for book in Book.objects.filter(id__in=ordered_ids).prefetch_related(
                "group_assignments"
            )
        }
        visible_books: list[Book] = []
        for book_id in ordered_ids:
            book = books_by_id.get(book_id)
            if book is None:
                continue
            if not policies.can_view_book(user=request.user, book=book):
                continue
            visible_books.append(book)

        return Response(
            {"results": reading_activity_summary_for_books(user=request.user, books=visible_books)},
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
        BasicAuthentication,
        ClientBearerAuthentication,
    ]
    permission_classes = [IsAuthenticated]

    def post(self, request, book_id):
        created = False

        # Preserve durability behavior: if an active session exists, return it even
        # if current book access is lost.
        session = ReadingSession.objects.select_related("book").filter(
            user=request.user, book_id=book_id, is_active=True
        ).first()

        if session is None:
            book = get_object_or_404(Book, id=book_id)
            if not policies.can_view_book(user=request.user, book=book):
                raise NotFound()
            session = get_or_create_active_session(user=request.user, book=book)
            created = True

        payload = _build_open_response_payload(request=request, session=session, view=self)

        return Response(
            payload, status=(status.HTTP_201_CREATED if created else status.HTTP_200_OK)
        )


