from __future__ import annotations


INVALID_EPUB_MESSAGE = "Invalid or unsupported EPUB file."
UNSUPPORTED_SOURCE_MESSAGE = "Unsupported import source."
INVALID_ZIP_MESSAGE = "Invalid or unsupported ZIP archive."
UNSAFE_ARCHIVE_MEMBER_MESSAGE = "Unsafe archive member skipped."
UNEXPECTED_IMPORT_ERROR_MESSAGE = "Unexpected import failure."


class ImportErrorBase(ValueError):
    safe_message = UNEXPECTED_IMPORT_ERROR_MESSAGE

    def __init__(self, message: str | None = None):
        super().__init__(message or self.safe_message)


class InvalidEpubImportError(ImportErrorBase):
    safe_message = INVALID_EPUB_MESSAGE


class UnsupportedImportSourceError(ImportErrorBase):
    safe_message = UNSUPPORTED_SOURCE_MESSAGE


class InvalidZipImportError(ImportErrorBase):
    safe_message = INVALID_ZIP_MESSAGE


class UnsafeArchiveMemberError(ImportErrorBase):
    safe_message = UNSAFE_ARCHIVE_MEMBER_MESSAGE


def safe_import_message(exc: object) -> str:
    if isinstance(exc, ImportErrorBase):
        return exc.safe_message
    return UNEXPECTED_IMPORT_ERROR_MESSAGE


def operator_import_detail(exc: object) -> str:
    if exc is None:
        return ""
    if not isinstance(exc, ImportErrorBase):
        return exc.__class__.__name__
    message = str(exc or "").replace("\r", " ").replace("\n", " ").strip()
    if not message:
        return exc.__class__.__name__
    return f"{exc.__class__.__name__}: {message}"
