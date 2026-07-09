from __future__ import annotations

import hashlib
from uuid import uuid4
from dataclasses import dataclass
from typing import Any

from django.core.files.base import ContentFile

from library.groups.services import ensure_book_public_assignment
from library.models import Book


@dataclass(frozen=True)
class FileBackedBook:
    book: Book
    book_file: Any


def create_file_backed_book(
    *,
    title: str = "Test Book",
    epub_bytes: bytes = b"dummy epub",
    source_filename: str = "dummy.epub",
    assign_public: bool = True,
    book_fields: dict | None = None,
) -> FileBackedBook:
    """
    Test helper: create a minimal Book with Book-owned file fields.

    The product invariant is that Books are file-backed; tests should use this
    helper instead of creating fileless Books unless explicitly testing an
    internal escape hatch.
    """
    fields = dict(book_fields or {})
    fields.setdefault("title", title)
    if epub_bytes == b"dummy epub":
        epub_bytes = f"dummy epub:{title}:{source_filename}:{uuid4()}".encode()
    checksum = hashlib.sha256(epub_bytes).hexdigest()
    fields.setdefault("checksum", checksum)
    fields.setdefault("file_size", len(epub_bytes))
    fields.setdefault("source_filename", source_filename)
    book = Book.objects.create(**fields)
    book.book_file.save(source_filename, ContentFile(epub_bytes), save=True)
    if assign_public:
        ensure_book_public_assignment(book=book, added_by=None)

    book_file = book.book_file
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
