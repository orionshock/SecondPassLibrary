from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework.exceptions import NotFound
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from library.models import Book

from .api import (
    MarginaliaReadMixin,
    book_access_required_response,
    invalid_request_response,
    session_closed_response,
)
from .bootstrap import bootstrap_envelope
from .bootstrap_serializers import MarginaliaOpenSerializer, MarginaliaStartOverSerializer
from .detail_views import session_detail_response
from .exceptions import (
    BookAccessRequiredError,
    FinalizationWithoutActiveSessionError,
    IdempotencyConflictError,
    IdempotencyInProgressError,
    SessionClosedError,
)
from .idempotency import (
    execute_idempotent,
    normalized_request_hash,
    validate_idempotency_key,
)
from .lifecycle_services import (
    active_session_for_accessible_book,
    close_owned_session,
    open_or_create_session,
    replace_progress,
    start_over_session,
)
from .models import ReadingSession
from .progress_serializers import (
    MarginaliaProgressPutSerializer,
    MarginaliaSessionCloseSerializer,
    progress_envelope,
)


class MarginaliaSessionProgressView(MarginaliaReadMixin, APIView):
    def get(self, request, session_id):
        session = get_object_or_404(
            ReadingSession.objects.only(
                "progress_cfi",
                "progress_location_label",
                "progress_updated_at",
            ),
            pk=session_id,
            user=request.user,
        )
        return Response(progress_envelope(session))

    def put(self, request, session_id):
        serializer = MarginaliaProgressPutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            session = replace_progress(
                user=request.user,
                session_id=session_id,
                **serializer.validated_data,
            )
        except ReadingSession.DoesNotExist as exc:
            raise NotFound from exc
        except SessionClosedError:
            return session_closed_response()
        except BookAccessRequiredError:
            return book_access_required_response()
        return Response(progress_envelope(session))


class MarginaliaSessionCloseView(MarginaliaReadMixin, APIView):
    def post(self, request, session_id):
        serializer = MarginaliaSessionCloseSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        metadata = {
            field: values[field]
            for field in ("name", "notes")
            if field in values
        }
        try:
            session = close_owned_session(
                user=request.user,
                session_id=session_id,
                metadata=metadata,
                progress=values.get("progress"),
            )
        except ReadingSession.DoesNotExist as exc:
            raise NotFound from exc
        except SessionClosedError:
            return session_closed_response()
        except BookAccessRequiredError:
            return book_access_required_response()
        return session_detail_response(request=request, session_id=session.pk)


class MarginaliaBookOpenView(MarginaliaReadMixin, APIView):
    def post(self, request, book_id):
        serializer = MarginaliaOpenSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        try:
            session, created = open_or_create_session(
                user=request.user,
                book_id=book_id,
                defaults=serializer.validated_data,
            )
        except (BookAccessRequiredError, Book.DoesNotExist) as exc:
            raise NotFound from exc
        payload = bootstrap_envelope(
            request=request,
            book_id=book_id,
            session_id=session.pk,
            created=created,
        )
        response_status = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(payload, status=response_status)


class MarginaliaBookActiveSessionView(MarginaliaReadMixin, APIView):
    def get(self, request, book_id):
        try:
            session = active_session_for_accessible_book(
                user=request.user,
                book_id=book_id,
            )
        except (BookAccessRequiredError, Book.DoesNotExist) as exc:
            raise NotFound from exc
        payload = bootstrap_envelope(
            request=request,
            book_id=book_id,
            session_id=session.pk if session is not None else None,
            created=False,
        )
        return Response(payload)


class MarginaliaBookStartOverView(MarginaliaReadMixin, APIView):
    def post(self, request, book_id):
        serializer = MarginaliaStartOverSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        try:
            key = validate_idempotency_key(request.headers.get("Idempotency-Key"))
        except ValueError:
            return invalid_request_response(
                message="A valid Idempotency-Key header is required."
            )
        request_hash = normalized_request_hash(
            method=request.method,
            path=request.path,
            data=serializer.validated_data,
        )

        def operation():
            session = start_over_session(
                user=request.user,
                book_id=book_id,
                finalization=serializer.validated_data,
            )
            return bootstrap_envelope(
                request=request,
                book_id=book_id,
                session_id=session.pk,
                created=True,
            )

        try:
            payload = execute_idempotent(
                user=request.user,
                key=key,
                method=request.method,
                path=request.path,
                request_hash=request_hash,
                operation=operation,
            )
        except (BookAccessRequiredError, Book.DoesNotExist) as exc:
            raise NotFound from exc
        except FinalizationWithoutActiveSessionError:
            return invalid_request_response(
                message="Final Session values require an active Session.",
                status_code=status.HTTP_409_CONFLICT,
            )
        except IdempotencyConflictError:
            return invalid_request_response(
                message="Idempotency-Key was already used for a different request.",
                status_code=status.HTTP_409_CONFLICT,
            )
        except IdempotencyInProgressError:
            return invalid_request_response(
                message="The Idempotency-Key request is still processing.",
                status_code=status.HTTP_409_CONFLICT,
            )
        except SessionClosedError:
            return session_closed_response()
        return Response(payload, status=status.HTTP_201_CREATED)
