from __future__ import annotations

from dataclasses import dataclass
import logging
from uuid import uuid4

from django.core.files.base import ContentFile
from django.db import transaction

from library.imports.epub import read_file_with_sha256, validate_epub_bytes
from library.imports.errors import InvalidEpubImportError
from library.models import Book


logger = logging.getLogger(__name__)


class StoredEpubRepairError(ValueError):
    pass


class ReplaceExistingConfirmationRequired(StoredEpubRepairError):
    pass


class ChecksumChangeConfirmationRequired(StoredEpubRepairError):
    pass


class ChecksumCollisionError(StoredEpubRepairError):
    pass


@dataclass(frozen=True)
class StoredEpubRepairResult:
    previous_checksum: str | None
    new_checksum: str
    checksum_changed: bool
    file_size: int
    replaced_existing_file: bool
    restored_missing_file: bool


def repair_stored_epub(
    *,
    book: Book,
    uploaded_epub,
    replace_existing: bool,
    allow_checksum_change: bool,
    actor=None,
) -> StoredEpubRepairResult:
    upload_name = str(getattr(uploaded_epub, "name", "") or "")
    if not upload_name.casefold().endswith(".epub"):
        raise StoredEpubRepairError("The uploaded file must use the .epub extension.")

    data, new_checksum, file_size = read_file_with_sha256(uploaded_epub)
    try:
        validate_epub_bytes(data)
    except InvalidEpubImportError as exc:
        raise StoredEpubRepairError("Invalid or unsupported EPUB file.") from exc

    previous_checksum = book.checksum
    old_name = str(book.book_file.name or "")
    storage = book.book_file.storage
    current_file_exists = bool(old_name and storage.exists(old_name))
    checksum_changed = previous_checksum != new_checksum

    if current_file_exists and not replace_existing:
        raise ReplaceExistingConfirmationRequired(
            "The Book already has a stored EPUB. Confirm replacement to continue."
        )
    if previous_checksum and checksum_changed and not allow_checksum_change:
        raise ChecksumChangeConfirmationRequired(
            "The uploaded EPUB checksum differs from the Book checksum. "
            "Existing EPUB CFI anchors may no longer match; explicitly confirm "
            "the checksum change to continue."
        )
    _reject_checksum_collision(book=book, checksum=new_checksum)

    staged_name = storage.save(
        _staged_storage_name(new_checksum),
        ContentFile(data),
    )
    try:
        with transaction.atomic():
            locked = Book.objects.select_for_update().get(pk=book.pk)
            if (
                locked.checksum != previous_checksum
                or str(locked.book_file.name or "") != old_name
            ):
                raise StoredEpubRepairError(
                    "The Book file state changed during repair. Reload and try again."
                )
            _reject_checksum_collision(book=locked, checksum=new_checksum)
            locked.book_file.name = staged_name
            locked.file_format = Book.FILE_FORMAT_EPUB
            locked.checksum = new_checksum
            locked.file_size = file_size
            locked.save(
                update_fields=[
                    "book_file",
                    "file_format",
                    "checksum",
                    "file_size",
                    "updated_at",
                ]
            )
            if current_file_exists and old_name != staged_name:
                transaction.on_commit(
                    lambda: _delete_unreferenced_file(
                        storage=storage,
                        file_name=old_name,
                    )
                )
    except Exception:
        _delete_staged_file(storage=storage, staged_name=staged_name)
        raise

    book.book_file.name = staged_name
    book.file_format = Book.FILE_FORMAT_EPUB
    book.checksum = new_checksum
    book.file_size = file_size

    if checksum_changed and previous_checksum:
        logger.warning(
            "Accepted changed EPUB checksum during repair for Book %s.",
            book.pk,
        )
    logger.info(
        "Stored EPUB repaired for Book %s: checksum_changed=%s outcome=%s "
        "size=%d",
        book.pk,
        checksum_changed,
        "replaced" if current_file_exists else "restored",
        file_size,
    )
    return StoredEpubRepairResult(
        previous_checksum=previous_checksum,
        new_checksum=new_checksum,
        checksum_changed=checksum_changed,
        file_size=file_size,
        replaced_existing_file=current_file_exists,
        restored_missing_file=not current_file_exists,
    )


def _reject_checksum_collision(*, book: Book, checksum: str) -> None:
    if Book.objects.exclude(pk=book.pk).filter(checksum=checksum).exists():
        raise ChecksumCollisionError(
            "Another Book already owns the uploaded EPUB checksum."
        )


def _staged_storage_name(checksum: str) -> str:
    return (
        f"books/{checksum[:2]}/{checksum[2:4]}/"
        f"{checksum}.repair-{uuid4().hex}.epub"
    )


def _delete_staged_file(*, storage, staged_name: str) -> None:
    try:
        if storage.exists(staged_name):
            storage.delete(staged_name)
    except Exception:
        logger.warning("Failed to clean a staged EPUB repair file.")


def _delete_unreferenced_file(*, storage, file_name: str) -> None:
    if not file_name or Book.objects.filter(book_file=file_name).exists():
        return
    try:
        if storage.exists(file_name):
            storage.delete(file_name)
    except Exception:
        logger.warning("Failed to clean an unreferenced replaced EPUB file.")
