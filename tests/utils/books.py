from __future__ import annotations

import hashlib
from dataclasses import dataclass

from django.core.files.base import ContentFile

from library.group_services import ensure_book_public_assignment
from library.models import Book, BookFile


@dataclass(frozen=True)
class FileBackedBook:
    book: Book
    book_file: BookFile


def create_file_backed_book(
    *,
    title: str = "Test Book",
    epub_bytes: bytes = b"dummy epub",
    source_filename: str = "dummy.epub",
    assign_public: bool = True,
    book_fields: dict | None = None,
) -> FileBackedBook:
    """
    Test helper: create a minimal valid Book + BookFile pair.

    The product invariant is that Books are file-backed; tests should use this
    helper instead of creating fileless Books unless explicitly testing an
    internal escape hatch.
    """
    fields = dict(book_fields or {})
    fields.setdefault("title", title)
    book = Book.objects.create(**fields)
    if assign_public:
        ensure_book_public_assignment(book=book, added_by=None)

    checksum = hashlib.sha256(epub_bytes).hexdigest()
    book_file = BookFile.objects.create(
        book=book,
        checksum=checksum,
        file=ContentFile(epub_bytes, name=source_filename),
        format=BookFile.FORMAT_EPUB,
        file_size=len(epub_bytes),
        source_filename=source_filename,
    )
    return FileBackedBook(book=book, book_file=book_file)


def create_fileless_book_for_integrity_edge_case(
    *, title: str = "Fileless Book", assign_public: bool = True, book_fields: dict | None = None
) -> Book:
    """
    Test helper for integrity edge cases only.

    Product policy: Books are file-backed. Use this only for tests that
    explicitly validate behavior around inconsistent/out-of-band states.
    """
    fields = dict(book_fields or {})
    fields.setdefault("title", title)
    book = Book.objects.create(**fields)
    if assign_public:
        ensure_book_public_assignment(book=book, added_by=None)
    return book
