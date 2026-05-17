from typing import Any, cast

from django.shortcuts import get_object_or_404
from rest_framework.exceptions import NotFound

from rest_framework import mixins, status, viewsets
from rest_framework.authentication import BasicAuthentication, SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from core.pagination import DefaultPageNumberPagination

from accounts.authentication import ClientBearerAuthentication

from library.models import Book
from core import policies

from .models import Annotation, ReadingProgress, ReadingSession
from .services import (
    assert_session_writable,
    close_session,
    get_or_create_active_session,
    get_or_create_progress,
    create_annotation,
    start_over_book,
    update_progress,
)
from .profile import CURRENT_READING_PROFILE_VERSION
from .w3c import build_publication_source
from .serializers import (
    AnnotationSerializer,
    ReadingProgressSerializer,
    ReadingSessionPatchSerializer,
    ReadingSessionSerializer,
)


def _build_open_response_payload(*, request: Request, session: ReadingSession, view) -> dict[str, Any]:
    progress = get_or_create_progress(session=session)

    annotations_qs = (
        Annotation.objects.select_related("session", "session__book")
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
        return ReadingSession.objects.select_related("book").filter(
            user=self.request.user
        )

    def get_serializer_class(self):
        if self.action == "partial_update":
            return ReadingSessionPatchSerializer
        return ReadingSessionSerializer

    def create(self, request, *args, **kwargs):
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def update(self, request, *args, **kwargs):
        # Disallow full PUT updates; only PATCH is supported for name/notes.
        if request.method.upper() == "PUT":
            return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)
        return super().update(request, *args, **kwargs)


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


class ReadingProgressViewSet(viewsets.GenericViewSet):
    authentication_classes = [
        SessionAuthentication,
        BasicAuthentication,
        ClientBearerAuthentication,
    ]
    serializer_class = ReadingProgressSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "session_id"

    def get_queryset(self):
        return ReadingProgress.objects.select_related("session").filter(
            session__user=self.request.user
        )

    def _get_session(self, session_id):
        return get_object_or_404(ReadingSession, id=session_id, user=self.request.user)

    def retrieve(self, request, session_id=None):
        session = self._get_session(session_id)
        progress = get_or_create_progress(session=session)
        return Response(ReadingProgressSerializer(progress, context={"request": request}).data)

    def partial_update(self, request, session_id=None):
        return self._update(request, session_id=session_id, partial=True)

    def update(self, request, session_id=None):
        return self._update(request, session_id=session_id, partial=False)

    def _update(self, request, session_id, partial):
        session = self._get_session(session_id)
        progress = get_or_create_progress(session=session)
        serializer = ReadingProgressSerializer(
            progress, data=request.data, partial=partial, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        validated = cast(dict[str, Any], serializer.validated_data)
        current_location = validated.get("current_location", progress.current_location)
        progression = validated.get("progression", progress.progression)
        profile_version = validated.get("profile_version", CURRENT_READING_PROFILE_VERSION)
        progress = update_progress(
            session=session,
            current_location=current_location,
            progression=progression,
        )
        if profile_version != CURRENT_READING_PROFILE_VERSION:
            # Serializer should already enforce this; keep as a safety belt.
            return Response(
                {"detail": f"Unsupported profile_version: {profile_version}."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(ReadingProgressSerializer(progress).data)


class AnnotationViewSet(viewsets.ModelViewSet):
    authentication_classes = [
        SessionAuthentication,
        BasicAuthentication,
        ClientBearerAuthentication,
    ]
    serializer_class = AnnotationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        request = cast(Request, self.request)
        queryset = Annotation.objects.select_related(
            "session", "session__book"
        ).filter(session__user=self.request.user)

        include_deleted = (
            (request.query_params.get("include_deleted") or "")
            .strip()
            .lower()
            in {"1", "true", "t", "yes", "y", "on"}
        )
        if not include_deleted:
            queryset = queryset.filter(is_deleted=False)

        session_id = request.query_params.get("session_id")
        book_id = request.query_params.get("book_id")
        if session_id:
            queryset = queryset.filter(session_id=session_id)
        if book_id:
            queryset = queryset.filter(session__book_id=book_id)
        return queryset

    def perform_create(self, serializer):
        validated = cast(dict[str, Any], serializer.validated_data)
        session = cast(ReadingSession, validated["session"])
        motivation = cast(str, validated["motivation"])
        target = cast(dict, validated.get("target") or {})
        body = validated.get("body") or []

        # Enrich a missing source deterministically based on the session book.
        if "source" not in target or not target.get("source"):
            target = dict(target)
            target["source"] = build_publication_source(book=session.book)

        annotation = create_annotation(
            session=session,
            motivation=motivation,
            target=target,
            body=body,
        )
        serializer.instance = annotation

    def perform_update(self, serializer):
        annotation = cast(Annotation, serializer.instance)
        assert_session_writable(session=annotation.session)
        serializer.save()

    def destroy(self, request, *args, **kwargs):
        annotation = self.get_object()
        annotation.is_deleted = True
        annotation.save(update_fields=["is_deleted", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)
