from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404

from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from library.models import Book

from .models import Annotation, Device, ReadingProgress, ReadingSession
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
        return ReadingSession.objects.select_related('book').filter(user=self.request.user)

    def get_serializer_class(self):
        if self.action in {'create', 'update', 'partial_update'}:
            return ReadingSessionCreateSerializer
        return ReadingSessionSerializer

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class ActiveSessionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, book_id):
        book = get_object_or_404(Book, id=book_id)
        try:
            with transaction.atomic():
                session, _created = ReadingSession.objects.get_or_create(
                    user=request.user,
                    book=book,
                    is_active=True,
                    defaults={'status': ReadingSession.STATUS_ACTIVE},
                )
        except IntegrityError:
            session = ReadingSession.objects.get(user=request.user, book=book, is_active=True)
        return Response(ReadingSessionSerializer(session).data)


class StartOverView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, book_id):
        book = get_object_or_404(Book, id=book_id)
        name = request.data.get('name', '')

        with transaction.atomic():
            (
                ReadingSession.objects.filter(user=request.user, book=book, is_active=True)
                .select_for_update()
                .update(is_active=False, status=ReadingSession.STATUS_ARCHIVED)
            )
            session = ReadingSession.objects.create(
                user=request.user,
                book=book,
                name=name or '',
                status=ReadingSession.STATUS_ACTIVE,
                is_active=True,
            )

        return Response(ReadingSessionSerializer(session).data, status=status.HTTP_201_CREATED)


class ReadingProgressViewSet(viewsets.GenericViewSet):
    serializer_class = ReadingProgressSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'session_id'

    def get_queryset(self):
        return ReadingProgress.objects.select_related('session', 'device').filter(session__user=self.request.user)

    def _get_session(self, session_id):
        return get_object_or_404(ReadingSession, id=session_id, user=self.request.user)

    def retrieve(self, request, session_id=None):
        session = self._get_session(session_id)
        progress, _ = ReadingProgress.objects.get_or_create(session=session, defaults={'locator': {}})
        return Response(ReadingProgressSerializer(progress).data)

    def partial_update(self, request, session_id=None):
        return self._update(request, session_id=session_id, partial=True)

    def update(self, request, session_id=None):
        return self._update(request, session_id=session_id, partial=False)

    def _update(self, request, session_id, partial):
        session = self._get_session(session_id)
        progress, _ = ReadingProgress.objects.get_or_create(session=session, defaults={'locator': {}})
        serializer = ReadingProgressSerializer(progress, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save(session=session)
        return Response(serializer.data)


class AnnotationViewSet(viewsets.ModelViewSet):
    serializer_class = AnnotationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = (
            Annotation.objects.select_related('session', 'session__book', 'device')
            .filter(session__user=self.request.user)
        )
        session_id = self.request.query_params.get('session_id')
        book_id = self.request.query_params.get('book_id')
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
        annotation.save(update_fields=['is_deleted', 'updated_at'])
        return Response(status=status.HTTP_204_NO_CONTENT)
