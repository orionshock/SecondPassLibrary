from __future__ import annotations

from functools import partial
import hashlib
import logging

from django.core.files.base import ContentFile
from django.db import transaction

from core.operational_logging import (
    info_on_commit,
    safe_log_label,
    user_log_label,
    user_uuid,
)
from library.imports.covers import (
    ExtractedCover,
    MAX_COVER_IMAGE_BYTES,
    validate_cover_bytes,
)
from library.models import Book
from library.storage_diagnostics import log_storage_issue


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
                transaction.on_commit(
                    partial(
                        _cleanup_old_cover,
                        name=old_name,
                        book_id=str(locked.pk),
                        operation="replace",
                        actor=actor,
                    )
                )
            if log_success:
                info_on_commit(
                    logger,
                    "Book cover changed: action=%s book_id=%s book=%s actor=%s "
                    "actor_profile_id=%s",
                    "book_cover_replace",
                    locked.pk,
                    safe_log_label(locked.title, fallback=str(locked.pk)),
                    user_log_label(actor),
                    user_uuid(actor),
                )
    except Exception:
        if created_file and not Book.objects.filter(cover_file=stored_name).exists():
            try:
                storage.delete(stored_name)
            except Exception as cleanup_exc:
                log_storage_issue(
                    logger,
                    action="new_cover_rollback_cleanup",
                    book_id=book.pk,
                    actor=actor,
                    reason="delete-failed",
                    exc=cleanup_exc,
                    storage_name=stored_name,
                )
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
                actor=actor,
            )
        )
        info_on_commit(
            logger,
            "Book cover changed: action=%s book_id=%s book=%s actor=%s "
            "actor_profile_id=%s",
            "book_cover_clear",
            locked.pk,
            safe_log_label(locked.title, fallback=str(locked.pk)),
            user_log_label(actor),
            user_uuid(actor),
        )

    book.cover_file.name = ""
    return book


def set_book_cover_from_bytes(*, book: Book, data: bytes, source: str = "") -> Book:
    """Low-level fixture/import compatibility helper; mutations use validated covers."""
    digest = hashlib.sha256(data).hexdigest()
    book.cover_file.save(f"{digest}.png", ContentFile(data), save=True)
    return book


def _cleanup_old_cover(
    *,
    name: str,
    book_id: str,
    operation: str,
    actor=None,
) -> None:
    referenced: bool | None = None
    try:
        referenced = Book.objects.filter(cover_file=name).exists()
        if referenced:
            logger.info(
                "Book cover cleanup skipped: action=old_cover_cleanup book_id=%s "
                "operation=%s actor=%s actor_profile_id=%s reason=still-referenced",
                book_id,
                operation,
                user_log_label(actor),
                user_uuid(actor),
            )
            return
        Book._meta.get_field("cover_file").storage.delete(name)
    except Exception as exc:
        log_storage_issue(
            logger,
            action="old_cover_cleanup",
            book_id=book_id,
            actor=actor,
            reason="delete-failed",
            exc=exc,
            storage_name=name,
            operation=operation,
            reference_state=(
                "unknown" if referenced is None else str(referenced).lower()
            ),
        )
