from __future__ import annotations

import logging

from django.http import Http404
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.roles import is_librarian
from core.errors import ErrorCode, api_error_response
from library.catalog.serializers.books import BookDetailSerializer
from library.catalog.views import attach_visible_groups_to_book, book_detail_queryset
from library.cover_services import (
    InvalidBookCover,
    clear_book_cover,
    replace_book_cover,
    validate_book_cover_upload,
)
from library.queries import visible_books_for_user
from library.storage_diagnostics import log_storage_issue


logger = logging.getLogger(__name__)


class BookCoverView(APIView):
    authentication_classes = [SessionAuthentication]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, book_id):
        book = self._get_book(request.user, book_id)
        self._require_librarian(request.user)
        upload = request.FILES.get("cover")
        if upload is None:
            raise ValidationError({"cover": ["Choose a cover image."]})
        try:
            cover = validate_book_cover_upload(upload)
        except InvalidBookCover as exc:
            raise ValidationError({"cover": [str(exc)]}) from exc
        try:
            replace_book_cover(book=book, cover=cover, actor=request.user)
        except Exception as exc:
            # Storage backends do not share a useful exception base class. Keep
            # this API boundary broad so internal details never escape.
            log_storage_issue(
                logger,
                action="book_cover_replace",
                book_id=book.pk,
                actor=request.user,
                reason="storage-error",
                exc=exc,
                storage_name=str(book.cover_file.name or ""),
            )
            return api_error_response(
                code=ErrorCode.BOOK_COVER_UNAVAILABLE,
                message="The book cover could not be updated.",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return self._book_response(request, book_id)

    def delete(self, request, book_id):
        book = self._get_book(request.user, book_id)
        self._require_librarian(request.user)
        try:
            clear_book_cover(book=book, actor=request.user)
        except Exception as exc:
            # See POST: bounded storage failures are part of this API boundary.
            log_storage_issue(
                logger,
                action="book_cover_clear",
                book_id=book.pk,
                actor=request.user,
                reason="storage-error",
                exc=exc,
                storage_name=str(book.cover_file.name or ""),
            )
            return api_error_response(
                code=ErrorCode.BOOK_COVER_UNAVAILABLE,
                message="The book cover could not be updated.",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return self._book_response(request, book_id)

    @staticmethod
    def _get_book(user, book_id):
        book = visible_books_for_user(user, cached=False).filter(pk=book_id).first()
        if book is None:
            raise Http404
        return book

    @staticmethod
    def _require_librarian(user) -> None:
        if not is_librarian(user):
            raise PermissionDenied("Not allowed.")

    @staticmethod
    def _book_response(request, book_id):
        book = book_detail_queryset(visible_books_for_user(request.user, cached=False)).get(
            pk=book_id
        )
        book = attach_visible_groups_to_book(book=book, user=request.user)
        payload = BookDetailSerializer(book, context={"request": request}).data
        return Response(payload, status=status.HTTP_200_OK)
