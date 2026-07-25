from __future__ import annotations

from functools import partial
import hashlib
import logging
from pathlib import PurePath
import re

from django.core.files.base import ContentFile
from django.db import transaction

from library.imports.covers import (
    ExtractedCover,
    MAX_COVER_IMAGE_BYTES,
    validate_cover_bytes,
)
from library.models import Book


logger = logging.getLogger(__name__)

_LONG_HEX_RE = re.compile(r"[0-9a-fA-F]{32,}")

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
                transaction.on_commit(
                    partial(
                        _cleanup_old_cover,
                        name=old_name,
                        book_id=str(locked.pk),
                        operation="replace",
                    )
                )
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
        transaction.on_commit(
            partial(
                _cleanup_old_cover,
                name=old_name,
                book_id=str(locked.pk),
                operation="clear",
            )
        )
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


def _cleanup_old_cover(*, name: str, book_id: str, operation: str) -> None:
    referenced: bool | None = None
    try:
        referenced = Book.objects.filter(cover_file=name).exists()
        if referenced:
            logger.info(
                "Book cover cleanup skipped: book_id=%s operation=%s "
                "reason=still-referenced",
                book_id,
                operation,
            )
            return
        Book._meta.get_field("cover_file").storage.delete(name)
    except Exception as exc:
        logger.warning(
            "Book cover cleanup failed: book_id=%s operation=%s "
            "still_referenced=%s error=%s message=%s",
            book_id,
            operation,
            "unknown" if referenced is None else str(referenced).lower(),
            type(exc).__name__,
            _safe_cleanup_error_message(exc, cover_name=name),
        )


def _safe_cleanup_error_message(exc: Exception, *, cover_name: str) -> str:
    message = getattr(exc, "strerror", None) or str(exc) or "No error message."
    message = " ".join(str(message).split())
    secrets = {cover_name, PurePath(cover_name).name}
    for secret in secrets:
        if secret:
            message = message.replace(secret, "[redacted]")
    message = " ".join(
        "[redacted]" if "/" in token or "\\" in token else token
        for token in message.split()
    )
    return _LONG_HEX_RE.sub("[redacted]", message)[:160]


def _book_label(book: Book) -> str:
    return str(book.title or book.pk)


def _actor_label(actor) -> str:
    return str(getattr(actor, "username", "") or getattr(actor, "pk", "unknown"))


def _log_cover_change(action: str, book_label: str, actor_label: str) -> None:
    logger.info("Book cover %s: book=%s actor=%s", action, book_label, actor_label)
