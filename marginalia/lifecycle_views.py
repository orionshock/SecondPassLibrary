from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from .api import MarginaliaReadMixin
from .api_errors import book_access_required_response, session_closed_response
from .detail_views import session_detail_response
from .exceptions import BookAccessRequiredError, SessionClosedError
from .lifecycle_services import (
    close_owned_session,
    replace_progress,
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
