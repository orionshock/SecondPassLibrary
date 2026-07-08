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
from rest_framework.decorators import action

from accounts.authentication import ClientBearerAuthentication
from core.models import IdempotencyRecord

from ..models import HIGHLIGHT_COLOR_TOKENS, Annotation, ReadingSession
from ..policies import can_access_session_book
from ..serializers import AnnotationSerializer
from ..services import (
    assert_session_writable,
    create_annotation,
    update_annotation_content,
)


BATCH_CREATE_LIMIT = 100

class AnnotationViewSet(viewsets.ModelViewSet):
    authentication_classes = [
        SessionAuthentication,
        ClientBearerAuthentication,
    ]
    serializer_class = AnnotationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        request = cast(Request, self.request)
        queryset = Annotation.objects.select_related("session", "book").filter(
            session__user=self.request.user
        )

        include_deleted = (
            (request.query_params.get("include_deleted") or "")
            .strip()
            .lower()
            in {"1", "true", "t", "yes", "y", "on"}
        )
        if not include_deleted:
            queryset = queryset.filter(is_deleted=False)

        if "motivation" in request.query_params:
            raise DRFValidationError({"motivation": "Use kind instead."})

        kinds = [
            str(kind).strip()
            for kind in request.query_params.getlist("kind")
            if str(kind).strip()
        ]
        if kinds:
            allowed = {Annotation.ANCHOR_KIND_BOOKMARK, Annotation.ANCHOR_KIND_HIGHLIGHT}
            if any(kind not in allowed for kind in kinds):
                raise DRFValidationError({"kind": "Invalid kind."})
            q = Q()
            if Annotation.ANCHOR_KIND_BOOKMARK in kinds:
                q |= Q(anchor_kind=Annotation.ANCHOR_KIND_BOOKMARK)
            if Annotation.ANCHOR_KIND_HIGHLIGHT in kinds:
                q |= Q(anchor_kind=Annotation.ANCHOR_KIND_HIGHLIGHT)
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
        - comment_text
        - highlight_color
        """
        annotation = cast(Annotation, self.get_object())
        assert_session_writable(session=annotation.session)
        if not can_access_session_book(user=request.user, session=annotation.session):
            raise PermissionDenied("Book is not currently accessible.")

        initial = cast(dict[str, Any], getattr(request, "data", None) or {})
        allowed_keys = {"comment_text", "highlight_color"}
        unknown = set(initial.keys()).difference(allowed_keys)
        if unknown:
            unknown_sorted = ", ".join(sorted(unknown))
            raise DRFValidationError({"detail": f"Unsupported fields: {unknown_sorted}."})

        new_comment: str | None = None
        new_color: str | None = None

        if "comment_text" in initial:
            if annotation.anchor_kind != Annotation.ANCHOR_KIND_HIGHLIGHT:
                raise DRFValidationError({"comment_text": "Comments are only supported on highlights."})
            comment = initial.get("comment_text")
            if comment is not None and not isinstance(comment, str):
                raise DRFValidationError({"comment_text": "comment_text must be a string."})
            new_comment = comment or ""

        if "highlight_color" in initial:
            if annotation.anchor_kind != Annotation.ANCHOR_KIND_HIGHLIGHT:
                raise DRFValidationError({"highlight_color": "Highlight color applies only to highlights."})
            color = initial.get("highlight_color")
            if not isinstance(color, str):
                raise DRFValidationError({"highlight_color": "highlight_color must be a string."})
            token = color.strip()
            if token == "":
                raise DRFValidationError({"highlight_color": "highlight_color cannot be blank."})
            if token not in HIGHLIGHT_COLOR_TOKENS:
                raise DRFValidationError({"highlight_color": "Unsupported highlight_color token."})
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
        annotation = self._create_annotation_from_validated(validated)
        serializer.instance = annotation

    def _create_annotation_from_validated(self, validated: dict[str, Any]) -> Annotation:
        session = cast(ReadingSession, validated["session"])
        if not can_access_session_book(user=self.request.user, session=session):
            raise PermissionDenied("Book is not currently accessible.")
        selector = cast(dict[str, str], validated["selector"])
        quote = cast(dict[str, str], validated.get("quote") or {})
        return create_annotation(
            session=session,
            anchor_kind=cast(str, validated["anchor_kind"]),
            selector_kind=selector["kind"],
            selector_value=selector["value"],
            highlight_text=cast(str, validated.get("highlight_text") or ""),
            quote_prefix=quote.get("prefix") or "",
            quote_suffix=quote.get("suffix") or "",
            highlight_color=cast(str, validated.get("highlight_color") or ""),
            comment_text=cast(str, validated.get("comment_text") or ""),
        )

    @action(detail=False, methods=["post"], url_path="batch")
    def batch(self, request):
        data = cast(dict[str, Any], request.data or {})
        unknown = set(data.keys()).difference({"session", "annotations"})
        if unknown:
            unknown_sorted = ", ".join(sorted(unknown))
            raise DRFValidationError({"detail": f"Unsupported fields: {unknown_sorted}."})
        raw_session = data.get("session")
        raw_items = data.get("annotations")
        if not isinstance(raw_items, list):
            raise DRFValidationError({"annotations": "annotations must be a list."})
        if len(raw_items) > BATCH_CREATE_LIMIT:
            raise DRFValidationError(
                {"annotations": f"At most {BATCH_CREATE_LIMIT} annotations may be created at once."}
            )
        if not raw_items:
            raise DRFValidationError({"annotations": "annotations cannot be empty."})

        serializers: list[tuple[str | None, AnnotationSerializer]] = []
        for idx, item in enumerate(raw_items):
            if not isinstance(item, dict):
                raise DRFValidationError({"annotations": f"annotations[{idx}] must be an object."})
            item_unknown = set(item.keys()).difference(
                {"client_id", "kind", "selector", "quote", "highlight_text", "highlight_color", "comment_text"}
            )
            if item_unknown:
                unknown_sorted = ", ".join(sorted(item_unknown))
                raise DRFValidationError(
                    {"annotations": f"Unsupported fields in annotations[{idx}]: {unknown_sorted}."}
                )
            client_id = item.get("client_id")
            if client_id is not None and not isinstance(client_id, str):
                raise DRFValidationError({"annotations": f"annotations[{idx}].client_id must be a string."})
            payload = dict(item)
            payload.pop("client_id", None)
            payload["session"] = raw_session
            serializer = self.get_serializer(data=payload)
            serializer.is_valid(raise_exception=True)
            serializers.append((client_id, serializer))

        with transaction.atomic():
            response_items = []
            for client_id, serializer in serializers:
                annotation = self._create_annotation_from_validated(
                    cast(dict[str, Any], serializer.validated_data)
                )
                payload = AnnotationSerializer(annotation, context=self.get_serializer_context()).data
                if client_id is not None:
                    payload = dict(payload)
                    payload["client_id"] = client_id
                response_items.append(payload)
        return Response({"annotations": response_items}, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        annotation = self.get_object()
        assert_session_writable(session=annotation.session)
        if not can_access_session_book(user=request.user, session=annotation.session):
            raise PermissionDenied("Book is not currently accessible.")
        annotation.is_deleted = True
        annotation.save(update_fields=["is_deleted", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)
