from __future__ import annotations

import hashlib

from django.core.files.base import ContentFile

from library.models import Book


def set_book_cover_from_bytes(*, book: Book, data: bytes, source: str = "") -> Book:
    digest = hashlib.sha256(data).hexdigest()
    book.cover_file.save(f"{digest}.png", ContentFile(data), save=True)
    return book
