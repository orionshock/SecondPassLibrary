from __future__ import annotations

from dataclasses import dataclass
from django.core.exceptions import ValidationError
from django.core.files import File
from django.db import transaction
from pathlib import Path
import zipfile

from .epub_services import calculate_file_sha256
from .models import Book, BookFile


@dataclass(frozen=True)
class BookFileUploadMetadata:
    checksum: str
    file_size: int
    source_filename: str


@dataclass(frozen=True)
class BookFileRepairResult:
    book_file: BookFile
    created: bool
    replaced_existing_file: bool
    previous_checksum: str
    checksum_matched: bool


def _rewind(upload) -> None:
    seek = getattr(upload, "seek", None)
    if callable(seek):
        seek(0)


def _validate_epub_zip(upload) -> None:
    _rewind(upload)
    try:
        with zipfile.ZipFile(upload, "r") as zf:
            if not zf.infolist():
                raise ValueError
    except Exception:
        raise ValueError("Book file must be a valid EPUB file.") from None
    finally:
        _rewind(upload)


def inspect_epub_upload(upload) -> BookFileUploadMetadata:
    source_filename = Path(str(getattr(upload, "name", ""))).name
    if Path(source_filename).suffix.lower() != ".epub":
        raise ValueError("Book file must be an EPUB file.")

    _validate_epub_zip(upload)
    checksum, file_size = calculate_file_sha256(upload)
    return BookFileUploadMetadata(
        checksum=checksum,
        file_size=file_size,
        source_filename=source_filename,
    )


def book_file_storage_exists(book_file: BookFile) -> bool:
    if not book_file.file:
        return False
    try:
        return bool(book_file.file.storage.exists(book_file.file.name))
    except Exception:
        return False


def repair_book_file_for_book(
    *,
    book: Book,
    upload,
    replace_existing_file: bool = False,
    allow_checksum_mismatch: bool = False,
) -> BookFileRepairResult:
    """
    Attach or repair the EPUB file for an existing Book.

    This deliberately does not update Book metadata, identifiers, authors, cover,
    groups, shelves, sessions, or annotations.
    """
    metadata = inspect_epub_upload(upload)

    try:
        existing = book.file
    except BookFile.DoesNotExist:
        existing = None

    duplicate = BookFile.objects.filter(checksum=metadata.checksum)
    if existing is not None:
        duplicate = duplicate.exclude(pk=existing.pk)
    if duplicate.exists():
        raise ValidationError("An EPUB with this checksum is already stored.")

    previous_checksum = (existing.checksum or "") if existing is not None else ""
    checksum_matched = bool(previous_checksum and previous_checksum == metadata.checksum)
    existing_file_present = (
        book_file_storage_exists(existing) if existing is not None else False
    )

    if existing is not None and existing_file_present and not replace_existing_file:
        raise ValidationError(
            "This book already has a stored EPUB file. Confirm replacement to continue."
        )

    if (
        existing is not None
        and previous_checksum
        and previous_checksum != metadata.checksum
        and not allow_checksum_mismatch
    ):
        raise ValidationError(
            "Uploaded EPUB checksum does not match the existing BookFile checksum."
        )

    _rewind(upload)
    with transaction.atomic():
        if existing is None:
            book_file = BookFile(
                book=book,
                format=BookFile.FORMAT_EPUB,
                checksum=metadata.checksum,
                file_size=metadata.file_size,
                source_filename=metadata.source_filename,
            )
            book_file.file.save(
                f"{metadata.checksum}.epub",
                File(upload),
                save=False,
            )
            book_file.save()
            created = True
            replaced_existing_file = False
        else:
            old_name = existing.file.name if existing.file else ""
            existing.checksum = metadata.checksum
            existing.file_size = metadata.file_size
            existing.source_filename = metadata.source_filename
            existing.format = BookFile.FORMAT_EPUB
            existing.file.save(
                f"{metadata.checksum}.epub",
                File(upload),
                save=False,
            )
            existing.save(
                update_fields=[
                    "file",
                    "format",
                    "checksum",
                    "file_size",
                    "source_filename",
                    "updated_at",
                ]
            )
            if replace_existing_file and old_name and old_name != existing.file.name:
                try:
                    existing.file.storage.delete(old_name)
                except Exception:
                    pass
            book_file = existing
            created = False
            replaced_existing_file = True

    return BookFileRepairResult(
        book_file=book_file,
        created=created,
        replaced_existing_file=replaced_existing_file,
        previous_checksum=previous_checksum,
        checksum_matched=checksum_matched,
    )
