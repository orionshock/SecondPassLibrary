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
from library.storage_diagnostics import log_storage_issue


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
            log_storage_issue(
                logger,
                action="book_download",
                book_id=book.pk,
                actor=request.user,
                reason=(
                    "unsupported-format"
                    if book.file_format != Book.FILE_FORMAT_EPUB
                    else "missing-file-field"
                ),
            )
            return api_error_response(
                code=ErrorCode.BOOK_FILE_UNAVAILABLE,
                message="The EPUB file is unavailable.",
                status_code=status.HTTP_409_CONFLICT,
            )

        try:
            file_handle = book.book_file.storage.open(book.book_file.name, "rb")
        except Exception as exc:
            log_storage_issue(
                logger,
                action="book_download",
                book_id=book.pk,
                actor=request.user,
                reason="storage-error",
                exc=exc,
                storage_name=str(book.book_file.name or ""),
            )
            return api_error_response(
                code=ErrorCode.BOOK_FILE_UNAVAILABLE,
                message="The EPUB file is unavailable.",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

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
                    book=book,
                    user=request.user,
                )
            else:
                response.streaming_content = _file_iterator(
                    file_handle,
                    block_size=response.block_size,
                    book=book,
                    user=request.user,
                )
            return response
        except Exception as exc:
            try:
                file_handle.close()
            except Exception:
                pass
            log_storage_issue(
                logger,
                action="book_download",
                book_id=book.pk,
                actor=request.user,
                reason="storage-error",
                exc=exc,
                storage_name=str(book.book_file.name or ""),
            )
            return api_error_response(
                code=ErrorCode.BOOK_FILE_UNAVAILABLE,
                message="The EPUB file is unavailable.",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )


def _file_iterator(file_handle, *, block_size: int, book: Book, user):
    try:
        while chunk := file_handle.read(block_size):
            yield chunk
    except Exception as exc:
        log_storage_issue(
            logger,
            action="book_download",
            book_id=book.pk,
            actor=user,
            reason="storage-read-error",
            exc=exc,
            storage_name=str(book.book_file.name or ""),
        )
        raise


async def _async_file_iterator(
    file_handle,
    *,
    block_size: int,
    book: Book,
    user,
):
    read = sync_to_async(file_handle.read, thread_sensitive=False)
    try:
        while chunk := await read(block_size):
            yield chunk
    except Exception as exc:
        log_storage_issue(
            logger,
            action="book_download",
            book_id=book.pk,
            actor=user,
            reason="storage-read-error",
            exc=exc,
            storage_name=str(book.book_file.name or ""),
        )
        raise
