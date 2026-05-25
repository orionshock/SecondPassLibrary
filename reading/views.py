from typing import Any, cast

import hashlib
import json
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import NotFound
from rest_framework.exceptions import ValidationError as DRFValidationError

from rest_framework import mixins, status, viewsets
from rest_framework.authentication import BasicAuthentication, SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from core.pagination import DefaultPageNumberPagination
from rest_framework.renderers import JSONRenderer

from accounts.authentication import ClientBearerAuthentication

from django.db.models import Count, Max, Q, F
from django.db.models.functions import Coalesce, Greatest

from library.models import Book
from core import policies

from .models import Annotation, ReadingProgress, ReadingSession
from .services import (
    assert_session_writable,
    close_session,
    get_or_create_active_session,
    get_or_create_progress,
    create_annotation,
    update_annotation,
    start_over_book,
    update_progress,
)
from .profile import CURRENT_READING_PROFILE_VERSION
from .serializers import (
    AnnotationSerializer,
    ReadingProgressSerializer,
    ReadingSessionPatchSerializer,
    ReadingSessionSerializer,
    ReadingSessionSummarySerializer,
)
from core.models import IdempotencyRecord


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
            "session", "book", "book_file"
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

    def _validate_idempotency_key(self, raw: str) -> str:
        key = (raw or "").strip()
        if not key:
            raise DRFValidationError({"detail": "Idempotency-Key is required when provided."})
        if len(key) > 128:
            raise DRFValidationError({"detail": "Idempotency-Key is too long (max 128)."})
        # Reject control characters.
        for ch in key:
            o = ord(ch)
            if o < 32 or o == 127:
                raise DRFValidationError({"detail": "Idempotency-Key contains invalid characters."})
        return key

    def _request_hash(self, request: Request) -> str:
        data = request.data or {}
        try:
            body_json = json.dumps(data, sort_keys=True, separators=(",", ":"))
        except (TypeError, ValueError) as exc:
            raise DRFValidationError({"detail": "Request body is not JSON-serializable for idempotency."}) from exc
        payload = f"{request.method}\n{request.path}\n{body_json}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def create(self, request, *args, **kwargs):
        raw_key = request.headers.get("Idempotency-Key")
        if not raw_key:
            return super().create(request, *args, **kwargs)

        key = self._validate_idempotency_key(raw_key)
        req_hash = self._request_hash(cast(Request, request))
        now = timezone.now()

        # Idempotency applies only after successful validation + create.
        # If validation fails, we do not store any record.
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        expires_at = now + timedelta(hours=24)

        with transaction.atomic():
            existing = (
                IdempotencyRecord.objects.select_for_update()
                .filter(user=request.user, key=key)
                .first()
            )

            if existing is not None and existing.expires_at <= now:
                existing.delete()
                existing = None

            if existing is not None:
                if (
                    existing.method != request.method
                    or existing.path != request.path
                    or existing.request_hash != req_hash
                ):
                    return Response(
                        {"detail": "Idempotency-Key was already used for a different request."},
                        status=status.HTTP_409_CONFLICT,
                    )

                if (
                    existing.status == IdempotencyRecord.STATUS_COMPLETED
                    and existing.response_status is not None
                    and existing.response_body is not None
                ):
                    return Response(existing.response_body, status=int(existing.response_status))

                return Response(
                    {"detail": "Idempotency-Key request is still processing."},
                    status=status.HTTP_409_CONFLICT,
                )

            # Create a processing record to prevent double-creates under retries.
            try:
                record = IdempotencyRecord.objects.create(
                    user=request.user,
                    key=key,
                    method=request.method,
                    path=request.path,
                    request_hash=req_hash,
                    status=IdempotencyRecord.STATUS_PROCESSING,
                    expires_at=expires_at,
                )
            except IntegrityError:
                # Race: another request created the record. Re-check under lock.
                raced = (
                    IdempotencyRecord.objects.select_for_update()
                    .filter(user=request.user, key=key)
                    .first()
                )
                if raced is None:
                    raise
                if raced.expires_at <= now:
                    raced.delete()
                    return self.create(request, *args, **kwargs)
                if (
                    raced.method != request.method
                    or raced.path != request.path
                    or raced.request_hash != req_hash
                ):
                    return Response(
                        {"detail": "Idempotency-Key was already used for a different request."},
                        status=status.HTTP_409_CONFLICT,
                    )
                if (
                    raced.status == IdempotencyRecord.STATUS_COMPLETED
                    and raced.response_status is not None
                    and raced.response_body is not None
                ):
                    return Response(raced.response_body, status=int(raced.response_status))
                return Response(
                    {"detail": "Idempotency-Key request is still processing."},
                    status=status.HTTP_409_CONFLICT,
                )

            # Perform create using the already-validated serializer.
            self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            # Store a JSON-serializable copy (DRF serializer.data may contain UUID objects).
            rendered = JSONRenderer().render(serializer.data)
            response_body = cast(Any, json.loads(rendered.decode("utf-8")))

            record.status = IdempotencyRecord.STATUS_COMPLETED
            record.response_status = status.HTTP_201_CREATED
            record.response_body = response_body
            record.save(update_fields=["status", "response_status", "response_body", "updated_at"])

        return Response(response_body, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer):
        validated = cast(dict[str, Any], serializer.validated_data)
        session = cast(ReadingSession, validated["session"])
        motivation = cast(str, validated["motivation"])
        target = cast(dict, validated.get("target") or {})
        body = cast(list[dict], validated.get("body") or [])

        compact = serializer._compact_from_profile(target=target, body=body)  # type: ignore[attr-defined]
        annotation = create_annotation(session=session, motivation=motivation, **compact)
        serializer.instance = annotation

    def perform_update(self, serializer):
        annotation = cast(Annotation, serializer.instance)
        validated = cast(dict[str, Any], serializer.validated_data)
        motivation = cast(str, validated.get("motivation") or annotation.motivation or "")
        target = cast(dict, validated.get("target") or {})
        body = cast(list[dict], validated.get("body") or [])

        compact = serializer._compact_from_profile(target=target, body=body)  # type: ignore[attr-defined]
        update_annotation(annotation=annotation, motivation=motivation, **compact)

    def destroy(self, request, *args, **kwargs):
        annotation = self.get_object()
        annotation.is_deleted = True
        annotation.save(update_fields=["is_deleted", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)
