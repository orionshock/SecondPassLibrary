from __future__ import annotations

from functools import partial
import hashlib
import logging

from django.core.files.base import ContentFile
from django.db import transaction

from library.imports.covers import (
    ExtractedCover,
    MAX_COVER_IMAGE_BYTES,
    validate_cover_bytes,
)
from library.models import Book


logger = logging.getLogger(__name__)

COVER_VALIDATION_MESSAGE = (
    "Upload a valid JPEG, PNG, or WebP image no larger than 10 MiB "
    "or 20 million pixels."
)


class InvalidBookCover(ValueError):
    pass


def validate_book_cover_upload(upload) -> ExtractedCover:
    size = getattr(upload, "size", None)
    if size is not None and size > MAX_COVER_IMAGE_BYTES:
        raise InvalidBookCover(COVER_VALIDATION_MESSAGE)

    data = upload.read(MAX_COVER_IMAGE_BYTES + 1)
    cover = validate_cover_bytes(data)
    if cover is None:
        raise InvalidBookCover(COVER_VALIDATION_MESSAGE)
    return cover


def replace_book_cover(
    *,
    book: Book,
    cover: ExtractedCover,
    actor=None,
    log_success: bool = True,
) -> Book:
    field = Book._meta.get_field("cover_file")
    storage = field.storage
    digest = hashlib.sha256(cover.data).hexdigest()
    target_name = field.generate_filename(book, f"{digest}{cover.extension}")
    stored_name = target_name
    created_file = False

    if not storage.exists(target_name):
        stored_name = storage.save(target_name, ContentFile(cover.data))
        created_file = True

    try:
        with transaction.atomic():
            locked = Book.objects.select_for_update().get(pk=book.pk)
            old_name = str(locked.cover_file.name or "")
            locked.cover_file.name = stored_name
            locked.save(update_fields=["cover_file", "updated_at"])
            if old_name and old_name != stored_name:
                transaction.on_commit(partial(_delete_unreferenced_cover, old_name))
            if log_success:
                transaction.on_commit(
                    partial(
                        _log_cover_change,
                        "replaced",
                        _book_label(locked),
                        _actor_label(actor),
                    )
                )
    except Exception:
        if created_file and not Book.objects.filter(cover_file=stored_name).exists():
            storage.delete(stored_name)
        raise

    book.cover_file.name = stored_name
    return book


def clear_book_cover(*, book: Book, actor=None) -> Book:
    with transaction.atomic():
        locked = Book.objects.select_for_update().get(pk=book.pk)
        old_name = str(locked.cover_file.name or "")
        if not old_name:
            book.cover_file.name = ""
            return book

        locked.cover_file = ""
        locked.save(update_fields=["cover_file", "updated_at"])
        transaction.on_commit(partial(_delete_unreferenced_cover, old_name))
        transaction.on_commit(
            partial(
                _log_cover_change,
                "cleared",
                _book_label(locked),
                _actor_label(actor),
            )
        )

    book.cover_file.name = ""
    return book


def set_book_cover_from_bytes(*, book: Book, data: bytes, source: str = "") -> Book:
    """Low-level fixture/import compatibility helper; mutations use validated covers."""
    digest = hashlib.sha256(data).hexdigest()
    book.cover_file.save(f"{digest}.png", ContentFile(data), save=True)
    return book


def _delete_unreferenced_cover(name: str) -> None:
    if Book.objects.filter(cover_file=name).exists():
        return
    Book._meta.get_field("cover_file").storage.delete(name)


def _book_label(book: Book) -> str:
    return str(book.title or book.pk)


def _actor_label(actor) -> str:
    return str(getattr(actor, "username", "") or getattr(actor, "pk", "unknown"))


def _log_cover_change(action: str, book_label: str, actor_label: str) -> None:
    logger.info("Book cover %s: book=%s actor=%s", action, book_label, actor_label)
