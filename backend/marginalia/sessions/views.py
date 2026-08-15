from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from marginalia.api import (
    MarginaliaReadMixin,
    SessionAuthenticationRequiredForSessionDelete,
    book_access_required_response,
    session_closed_response,
)
from marginalia.books.queries import marginalia_books_for_user
from marginalia.books.serializers import MarginaliaBookSummarySerializer
from marginalia.exceptions import BookAccessRequiredError, SessionClosedError
from marginalia.models import ReadingSession

from .deletion import delete_owned_session
from .envelopes import session_detail_envelope
from .metadata import ClosedSessionMutationError, update_session_metadata
from .progress import replace_progress
from .queries import (
    marginalia_session_for_user,
    marginalia_sessions_for_book,
    marginalia_sessions_for_user,
    recent_marginalia_sessions_for_user,
)
from .serializers import (
    MarginaliaGlobalSessionSummarySerializer,
    MarginaliaAnnotationPresenceQuerySerializer,
    MarginaliaProgressPutSerializer,
    MarginaliaRecentSessionsQuerySerializer,
    MarginaliaRecentSessionSerializer,
    MarginaliaSessionMetadataPatchSerializer,
    MarginaliaSessionSummarySerializer,
    progress_envelope,
)


class MarginaliaBookSessionListView(MarginaliaReadMixin, ListAPIView):
    serializer_class = MarginaliaSessionSummarySerializer

    def get_parent_book(self):
        if not hasattr(self, "_parent_book"):
            self._parent_book = get_object_or_404(
                marginalia_books_for_user(user=self.request.user),
                pk=self.kwargs["book_id"],
            )
        return self._parent_book

    def get_queryset(self):
        return marginalia_sessions_for_book(
            user=self.request.user,
            book=self.get_parent_book(),
            status=self.request.query_params.get("status", ""),
            q=self.request.query_params.get("q", ""),
        )

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page, many=True)
        response = self.get_paginated_response(serializer.data)
        results = response.data.pop("results")
        response.data["context"] = {
            "book": MarginaliaBookSummarySerializer(
                self.get_parent_book(),
                context={"request": request},
            ).data
        }
        response.data["results"] = results
        return response


class MarginaliaSessionListView(MarginaliaReadMixin, ListAPIView):
    serializer_class = MarginaliaGlobalSessionSummarySerializer

    def get_queryset(self):
        presence = MarginaliaAnnotationPresenceQuerySerializer(
            data={
                "has_annotations": self.request.query_params.get("has_annotations")
            }
            if "has_annotations" in self.request.query_params
            else {}
        )
        presence.is_valid(raise_exception=True)
        return marginalia_sessions_for_user(
            user=self.request.user,
            status=self.request.query_params.get("status", ""),
            q=self.request.query_params.get("q", ""),
            has_annotations=presence.validated_data.get("has_annotations"),
        )


class MarginaliaRecentSessionListView(MarginaliaReadMixin, APIView):
    def get(self, request):
        query = MarginaliaRecentSessionsQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        sessions = recent_marginalia_sessions_for_user(
            user=request.user,
            **query.validated_data,
        )
        return Response(
            {
                "results": MarginaliaRecentSessionSerializer(
                    sessions,
                    many=True,
                    context={"request": request},
                ).data
            }
        )


class MarginaliaSessionDetailView(MarginaliaReadMixin, APIView):
    permission_classes = [
        *MarginaliaReadMixin.permission_classes,
        SessionAuthenticationRequiredForSessionDelete,
    ]

    def get_session(self):
        return get_object_or_404(
            marginalia_session_for_user(
                user=self.request.user,
                session_id=self.kwargs["session_id"],
            )
        )

    def get(self, request, *args, **kwargs):
        return Response(
            session_detail_envelope(
                request=request,
                session_id=self.kwargs["session_id"],
            ),
            status=status.HTTP_200_OK,
        )

    def patch(self, request, *args, **kwargs):
        session = self.get_session()
        serializer = MarginaliaSessionMetadataPatchSerializer(
            data=request.data or {},
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        try:
            update_session_metadata(
                session=session,
                changes=serializer.validated_data,
            )
        except ClosedSessionMutationError as exc:
            raise ValidationError(
                {"detail": "Closed Sessions are read-only."}
            ) from exc

        return Response(
            session_detail_envelope(request=request, session_id=session.pk),
            status=status.HTTP_200_OK,
        )

    def delete(self, request, session_id):
        try:
            delete_owned_session(user=request.user, session_id=session_id)
        except ReadingSession.DoesNotExist as exc:
            raise NotFound from exc
        return Response(status=status.HTTP_204_NO_CONTENT)


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
