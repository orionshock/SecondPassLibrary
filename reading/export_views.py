from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import NotFound

from core import policies
from library.models import Book

from .export_services import export_book_marginalia, export_session_marginalia
from .models import ReadingSession


class BookMarginaliaExportView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, book_id):
        book = get_object_or_404(
            Book.objects.select_related("series").prefetch_related("authors", "identifiers"),
            id=book_id,
        )
        if not policies.can_view_book(user=request.user, book=book):
            raise NotFound()
        return Response(export_book_marginalia(user=request.user, book=book))


class SessionMarginaliaExportView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, book_id, session_id):
        book = get_object_or_404(
            Book.objects.select_related("series").prefetch_related("authors", "identifiers"),
            id=book_id,
        )
        if not policies.can_view_book(user=request.user, book=book):
            raise NotFound()

        session = get_object_or_404(ReadingSession, id=session_id, user=request.user)
        if session.book_id != book.id:
            raise NotFound()

        return Response(
            export_session_marginalia(user=request.user, book=book, session=session)
        )
