from typing import Any, cast

from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.authentication import ClientBearerAuthentication

from .models import ReadingProgress, ReadingSession
from .profile import CURRENT_READING_PROFILE_VERSION
from .serializers import ReadingProgressSerializer
from .services import get_or_create_progress, is_session_closed, update_progress

class ReadingProgressViewSet(viewsets.GenericViewSet):
    authentication_classes = [
        SessionAuthentication,
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
        if is_session_closed(session):
            progress = ReadingProgress.objects.filter(session=session).first()
            if progress is None:
                progress = ReadingProgress(session=session, current_location={})
        else:
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


