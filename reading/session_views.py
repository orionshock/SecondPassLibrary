from typing import Any, cast

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
        BasicAuthentication,
        ClientBearerAuthentication,
    ]
    permission_classes = [IsAuthenticated]

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

        raw_book = (request.query_params.get("book") or "").strip()
        if raw_book:
            try:
                # UUID validation (accepts canonical string only).
                import uuid

                book_id = uuid.UUID(raw_book)
            except Exception:
                raise DRFValidationError({"book": "Invalid book id."})
            qs = qs.filter(book_id=book_id)

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

        return qs.order_by("-started_at")

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


