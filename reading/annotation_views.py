from typing import Any, cast

import hashlib
import json
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import PermissionDenied
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import JSONRenderer
from rest_framework.request import Request
from rest_framework.response import Response

from accounts.authentication import ClientBearerAuthentication
from core.models import IdempotencyRecord

from .annotation_profile_services import compact_annotation_from_profile
from .models import HIGHLIGHT_COLOR_TOKENS, Annotation, ReadingSession
from .policies import can_access_session_book
from .profile import validate_annotation_body, validate_profile_version
from .serializers import AnnotationSerializer
from .services import (
    assert_session_writable,
    create_annotation,
    update_annotation,
    update_annotation_content,
)

class AnnotationViewSet(viewsets.ModelViewSet):
    authentication_classes = [
        SessionAuthentication,
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

        motivations = [
            str(m).strip()
            for m in request.query_params.getlist("motivation")
            if str(m).strip()
        ]
        if motivations:
            allowed = {c[0] for c in Annotation.MOTIVATION_CHOICES}
            if any(m not in allowed for m in motivations):
                raise DRFValidationError({"motivation": "Invalid motivation."})
            q = Q()
            if Annotation.MOTIVATION_BOOKMARKING in motivations:
                q |= Q(anchor_kind=Annotation.ANCHOR_KIND_BOOKMARK)
            if Annotation.MOTIVATION_HIGHLIGHTING in motivations:
                q |= Q(anchor_kind=Annotation.ANCHOR_KIND_HIGHLIGHT)
            if Annotation.MOTIVATION_COMMENTING in motivations:
                q |= Q(
                    anchor_kind=Annotation.ANCHOR_KIND_HIGHLIGHT,
                    comment_text__gt="",
                )
            queryset = queryset.filter(q)

        session_id = request.query_params.get("session_id")
        book_id = request.query_params.get("book_id")
        if session_id:
            queryset = queryset.filter(session_id=session_id)
        if book_id:
            queryset = queryset.filter(session__book_id=book_id)

        ordering = (request.query_params.get("ordering") or "").strip()
        if ordering:
            mapping = {
                "created": ("created_at", "id"),
                "-created": ("-created_at", "-id"),
                "modified": ("updated_at", "id"),
                "-modified": ("-updated_at", "-id"),
            }
            order_by = mapping.get(ordering)
            if order_by is None:
                raise DRFValidationError({"ordering": "Invalid ordering."})
            return queryset.order_by(*order_by)

        # Keep ordering deterministic even when timestamps tie.
        return queryset.order_by("-created_at", "-id")

    def partial_update(self, request, *args, **kwargs):
        """
        Constrained PATCH semantics: anchors are immutable after creation.

        Allowed updates:
        - Comment/note text (TextualBody purpose=commenting value)
        - Highlight color token (TextualBody purpose=describing color)
        """
        annotation = cast(Annotation, self.get_object())
        assert_session_writable(session=annotation.session)
        if not can_access_session_book(user=request.user, session=annotation.session):
            raise PermissionDenied("Book is not currently accessible.")

        initial = cast(dict[str, Any], getattr(request, "data", None) or {})
        allowed_keys = {"body", "profile_version"}
        unknown = set(initial.keys()).difference(allowed_keys)
        if unknown:
            unknown_sorted = ", ".join(sorted(unknown))
            raise DRFValidationError({"detail": f"Unsupported fields: {unknown_sorted}."})

        try:
            validate_profile_version(initial.get("profile_version"))
        except ValueError as e:
            raise DRFValidationError({"profile_version": str(e)}) from e

        try:
            bodies = validate_annotation_body(initial.get("body"))
        except ValueError as e:
            raise DRFValidationError({"body": str(e)}) from e

        new_comment: str | None = None
        new_color: str | None = None

        for b in bodies:
            if b.get("type") != "TextualBody":
                continue
            purpose = str(b.get("purpose") or "").strip()
            value = b.get("value")
            color = b.get("color")

            if purpose == "commenting" and isinstance(value, str):
                new_comment = value
                continue

            if purpose == "describing":
                if (
                    value is not None
                    and isinstance(value, str)
                    and value
                    and value != (annotation.highlight_text or "")
                ):
                    raise DRFValidationError(
                        {"body": "describing body value is immutable for an annotation."}
                    )
                if color is not None:
                    if not isinstance(color, str):
                        raise DRFValidationError({"body": "describing body color must be a string."})
                    token = color.strip()
                    if token == "":
                        raise DRFValidationError({"body": "describing body color cannot be blank."})
                    if token not in HIGHLIGHT_COLOR_TOKENS:
                        raise DRFValidationError({"body": "Unsupported highlight color token."})
                    new_color = token

        update_annotation_content(
            annotation=annotation,
            comment_text=new_comment if new_comment is not None else None,
            highlight_color=new_color if new_color is not None else None,
        )

        return Response(AnnotationSerializer(annotation).data, status=status.HTTP_200_OK)

    def update(self, request, *args, **kwargs):
        # Disallow full PUT updates; PATCH has constrained semantics.
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)

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
        if not can_access_session_book(user=self.request.user, session=session):
            raise PermissionDenied("Book is not currently accessible.")
        motivations = cast(list[str], validated["motivation"])
        target = cast(dict, validated.get("target") or {})
        body = cast(list[dict], validated.get("body") or [])

        compact = compact_annotation_from_profile(motivations=motivations, target=target, body=body)
        anchor_kind = cast(str, compact.pop("anchor_kind"))
        annotation = create_annotation(session=session, anchor_kind=anchor_kind, **compact)
        serializer.instance = annotation

    def perform_update(self, serializer):
        annotation = cast(Annotation, serializer.instance)
        if not can_access_session_book(user=self.request.user, session=annotation.session):
            raise PermissionDenied("Book is not currently accessible.")
        validated = cast(dict[str, Any], serializer.validated_data)
        motivations = cast(list[str], validated.get("motivation") or [])
        target = cast(dict, validated.get("target") or {})
        body = cast(list[dict], validated.get("body") or [])

        compact = compact_annotation_from_profile(motivations=motivations, target=target, body=body)
        anchor_kind = cast(str, compact.pop("anchor_kind"))
        update_annotation(annotation=annotation, anchor_kind=anchor_kind, **compact)

    def destroy(self, request, *args, **kwargs):
        annotation = self.get_object()
        assert_session_writable(session=annotation.session)
        if not can_access_session_book(user=request.user, session=annotation.session):
            raise PermissionDenied("Book is not currently accessible.")
        annotation.is_deleted = True
        annotation.save(update_fields=["is_deleted", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)
