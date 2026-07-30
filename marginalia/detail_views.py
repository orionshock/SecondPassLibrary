from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .api import MarginaliaReadMixin
from .detail_serializers import (
    MarginaliaSessionDetailEnvelopeSerializer,
    MarginaliaSessionMetadataPatchSerializer,
)
from .metadata_services import ClosedSessionMutationError, update_session_metadata
from .queries import marginalia_books_for_user, marginalia_session_for_user


def session_detail_response(*, request, session_id) -> Response:
    session = get_object_or_404(
        marginalia_session_for_user(user=request.user, session_id=session_id)
    )
    book = get_object_or_404(
        marginalia_books_for_user(user=request.user),
        pk=session.book_id,
    )
    serializer = MarginaliaSessionDetailEnvelopeSerializer(
        {"context": {"book": book}, "session": session},
        context={"request": request},
    )
    return Response(serializer.data, status=status.HTTP_200_OK)


class MarginaliaSessionDetailView(MarginaliaReadMixin, APIView):
    def get_session(self):
        return get_object_or_404(
            marginalia_session_for_user(
                user=self.request.user,
                session_id=self.kwargs["session_id"],
            )
        )

    def get(self, request, *args, **kwargs):
        return session_detail_response(
            request=request,
            session_id=self.kwargs["session_id"],
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

        return session_detail_response(
            request=request,
            session_id=session.pk,
        )
