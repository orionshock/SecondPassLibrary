from typing import Any, cast

from django.shortcuts import get_object_or_404

from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from library.models import Book

from .models import Annotation, Device, ReadingProgress, ReadingSession
from .services import (
    get_or_create_active_session,
    get_or_create_progress,
    start_over_book,
    update_progress,
)
from .serializers import (
    AnnotationSerializer,
    DeviceSerializer,
    ReadingProgressSerializer,
    ReadingSessionCreateSerializer,
    ReadingSessionSerializer,
)


class DeviceViewSet(viewsets.ModelViewSet):
    serializer_class = DeviceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Device.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class ReadingSessionViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return ReadingSession.objects.select_related("book").filter(
            user=self.request.user
        )

    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return ReadingSessionCreateSerializer
        return ReadingSessionSerializer

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class ActiveSessionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, book_id):
        book = get_object_or_404(Book, id=book_id)
        session = get_or_create_active_session(user=request.user, book=book)
        return Response(ReadingSessionSerializer(session).data)


class StartOverView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, book_id):
        book = get_object_or_404(Book, id=book_id)
        name = request.data.get("name", "")
        session = start_over_book(user=request.user, book=book, name=name or "")
        return Response(
            ReadingSessionSerializer(session).data, status=status.HTTP_201_CREATED
        )


class ReadingProgressViewSet(viewsets.GenericViewSet):
    serializer_class = ReadingProgressSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "session_id"

    def get_queryset(self):
        return ReadingProgress.objects.select_related("session", "device").filter(
            session__user=self.request.user
        )

    def _get_session(self, session_id):
        return get_object_or_404(ReadingSession, id=session_id, user=self.request.user)

    def retrieve(self, request, session_id=None):
        session = self._get_session(session_id)
        progress = get_or_create_progress(session=session)
        return Response(ReadingProgressSerializer(progress).data)

    def partial_update(self, request, session_id=None):
        return self._update(request, session_id=session_id, partial=True)

    def update(self, request, session_id=None):
        return self._update(request, session_id=session_id, partial=False)

    def _update(self, request, session_id, partial):
        session = self._get_session(session_id)
        progress = get_or_create_progress(session=session)
        serializer = ReadingProgressSerializer(
            progress, data=request.data, partial=partial
        )
        serializer.is_valid(raise_exception=True)
        validated = cast(dict[str, Any], serializer.validated_data)
        locator = validated.get("locator", progress.locator)
        progression = validated.get("progression", progress.progression)
        device = validated.get("device", progress.device)
        progress = update_progress(
            session=session,
            locator=locator,
            progression=progression,
            device=device,
        )
        return Response(ReadingProgressSerializer(progress).data)


class AnnotationViewSet(viewsets.ModelViewSet):
    serializer_class = AnnotationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        request = cast(Request, self.request)
        queryset = Annotation.objects.select_related(
            "session", "session__book", "device"
        ).filter(session__user=self.request.user)
        session_id = request.query_params.get("session_id")
        book_id = request.query_params.get("book_id")
        if session_id:
            queryset = queryset.filter(session_id=session_id)
        if book_id:
            queryset = queryset.filter(session__book_id=book_id)
        return queryset

    def perform_create(self, serializer):
        serializer.save()

    def destroy(self, request, *args, **kwargs):
        annotation = self.get_object()
        annotation.is_deleted = True
        annotation.save(update_fields=["is_deleted", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)
