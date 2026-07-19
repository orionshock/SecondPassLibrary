from __future__ import annotations

import logging

from asgiref.sync import sync_to_async
from django.core.handlers.asgi import ASGIRequest
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.views import APIView

from core.errors import ErrorCode, api_error_response
from library.api_access import LibraryBearerReadMixin
from library.catalog.downloads import book_download_filename
from library.models import Book
from library.queries import visible_books_for_user


logger = logging.getLogger(__name__)

EPUB_CONTENT_TYPE = "application/epub+zip"


class BookDownloadView(LibraryBearerReadMixin, APIView):
    http_method_names = ["get", "head", "options"]

    def get(self, request, book_id):
        book = get_object_or_404(
            visible_books_for_user(request.user, cached=False),
            pk=book_id,
        )
        if book.file_format != Book.FILE_FORMAT_EPUB or not book.book_file:
            return _unavailable_response(status.HTTP_409_CONFLICT)

        try:
            file_handle = book.book_file.storage.open(book.book_file.name, "rb")
        except Exception as exc:
            return _storage_unavailable_response(book=book, user=request.user, exc=exc)

        try:
            response = FileResponse(
                file_handle,
                as_attachment=True,
                filename=book_download_filename(book.title),
                content_type=EPUB_CONTENT_TYPE,
            )
            if isinstance(request._request, ASGIRequest):
                response.streaming_content = _async_file_iterator(
                    file_handle,
                    block_size=response.block_size,
                )
            return response
        except Exception as exc:
            try:
                file_handle.close()
            except Exception:
                pass
            return _storage_unavailable_response(book=book, user=request.user, exc=exc)


def _unavailable_response(status_code: int):
    return api_error_response(
        code=ErrorCode.BOOK_FILE_UNAVAILABLE,
        message="The EPUB file is unavailable.",
        status_code=status_code,
    )


def _storage_unavailable_response(*, book: Book, user, exc: Exception):
    logger.warning(
        "Stored EPUB unavailable for book=%s actor=%s error=%s",
        _safe_label(book.title, book.pk),
        _safe_label(getattr(user, "username", ""), user.pk),
        type(exc).__name__,
    )
    return _unavailable_response(status.HTTP_503_SERVICE_UNAVAILABLE)


def _safe_label(value, fallback) -> str:
    return (" ".join(str(value or "").split()) or str(fallback))[:160]


async def _async_file_iterator(file_handle, *, block_size: int):
    read = sync_to_async(file_handle.read, thread_sensitive=False)
    while chunk := await read(block_size):
        yield chunk
