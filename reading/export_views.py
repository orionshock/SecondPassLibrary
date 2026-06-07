from __future__ import annotations

import re
from uuid import UUID

from django.shortcuts import get_object_or_404
from rest_framework.authentication import SessionAuthentication
from rest_framework.renderers import JSONRenderer
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import NotFound

from core import policies
from library.models import Book

from .export_services import (
    export_all_marginalia,
    export_book_marginalia,
    export_session_marginalia,
    selected_book_sessions,
)
from .models import ReadingSession


class PrettyJSONRenderer(JSONRenderer):
    def render(self, data, accepted_media_type=None, renderer_context=None):
        renderer_context = dict(renderer_context or {})
        renderer_context.setdefault("indent", 2)
        return super().render(data, accepted_media_type, renderer_context)


_FILENAME_UNSAFE_RE = re.compile(r"[^A-Za-z0-9._-]+")
_FILENAME_DASH_RE = re.compile(r"-+")


def _safe_filename_part(value: str, fallback: str) -> str:
    text = (value or "").strip()
    text = _FILENAME_UNSAFE_RE.sub("-", text)
    text = _FILENAME_DASH_RE.sub("-", text).strip(".-_")
    return text or fallback


def _download_response(payload: dict, filename: str) -> Response:
    response = Response(payload)
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def _parse_session_ids(raw_session_ids: list[str]) -> list[UUID]:
    try:
        return [UUID(value) for value in raw_session_ids]
    except (TypeError, ValueError):
        raise NotFound() from None


class AllMarginaliaExportView(APIView):
    authentication_classes = [SessionAuthentication]
    renderer_classes = [PrettyJSONRenderer]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        payload = export_all_marginalia(user=request.user)
        return _download_response(payload, "second-pass-marginalia.json")


class BookMarginaliaExportView(APIView):
    authentication_classes = [SessionAuthentication]
    renderer_classes = [PrettyJSONRenderer]
    permission_classes = [IsAuthenticated]

    def get(self, request, book_id):
        book = get_object_or_404(
            Book.objects.select_related("series").prefetch_related("authors", "identifiers"),
            id=book_id,
        )
        if not policies.can_view_book(user=request.user, book=book):
            raise NotFound()
        raw_session_ids = request.query_params.getlist("session")
        selected_sessions = None
        if raw_session_ids:
            try:
                selected_sessions = selected_book_sessions(
                    user=request.user,
                    book=book,
                    session_ids=_parse_session_ids(raw_session_ids),
                )
            except LookupError:
                raise NotFound() from None

        session_label = "selected-sessions" if raw_session_ids else "all-sessions"
        filename = f"{_safe_filename_part(book.title, 'book')}-{session_label}-marginalia.json"
        payload = export_book_marginalia(
            user=request.user,
            book=book,
            sessions=selected_sessions,
            selected=bool(raw_session_ids),
        )
        return _download_response(payload, filename)


class SessionMarginaliaExportView(APIView):
    authentication_classes = [SessionAuthentication]
    renderer_classes = [PrettyJSONRenderer]
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

        book_part = _safe_filename_part(book.title, "book")
        session_part = _safe_filename_part(session.name, "session")
        filename = f"{book_part}-{session_part}-marginalia.json"
        payload = export_session_marginalia(
            user=request.user, book=book, session=session
        )
        return _download_response(payload, filename)
