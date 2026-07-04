from __future__ import annotations

import logging
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from library.imports.epub import ImportStatus, import_epub
from library.imports.upload import MAX_SINGLE_EPUB_UPLOAD_BYTES, sanitize_import_error_message


logger = logging.getLogger(__name__)


def _format_mib(byte_count: int) -> str:
    return f"{byte_count // (1024 * 1024)} MiB"


def _log_extra(*, source_name: str, file_size: int | None = None) -> dict[str, object]:
    extra: dict[str, object] = {"source_name": source_name}
    if file_size is not None:
        extra["file_size"] = file_size
    return extra


def _format_log_value(value: object) -> str:
    return str(value).replace("\n", " ").replace("\r", " ")


def _operator_epub_log_message(
    *, event: str, source_name: str, status: str, safe_message: str | None = None
) -> str:
    message = (
        f"operator epub import {event} "
        f"source_name={_format_log_value(source_name)} "
        f"status={_format_log_value(status)}"
    )
    if safe_message is not None:
        message = f"{message} message={_format_log_value(safe_message)}"
    return message


class Command(BaseCommand):
    help = "Operator-only import for a single local EPUB file"

    def add_arguments(self, parser):
        parser.add_argument("file_path", type=str, help="Path to the EPUB file")

    def handle(self, *args, **options):
        file_path = options["file_path"]
        path = Path(file_path)
        source_name = path.name or file_path

        if not path.exists():
            message = f"File does not exist: {file_path}"
            self.stderr.write(self.style.ERROR(f"Failed to import EPUB: {message}"))
            logger.warning(
                _operator_epub_log_message(
                    event="failed",
                    source_name=source_name,
                    status="failed",
                    safe_message=message,
                ),
                extra={
                    **_log_extra(source_name=source_name),
                    "status": "failed",
                    "safe_message": message,
                },
            )
            raise CommandError(message)
        if path.suffix.lower() != ".epub":
            message = f"File must have .epub extension: {file_path}"
            self.stderr.write(self.style.ERROR(f"Failed to import EPUB: {message}"))
            logger.warning(
                _operator_epub_log_message(
                    event="failed",
                    source_name=source_name,
                    status="failed",
                    safe_message=message,
                ),
                extra={
                    **_log_extra(source_name=source_name, file_size=path.stat().st_size),
                    "status": "failed",
                    "safe_message": message,
                },
            )
            raise CommandError(message)

        file_size = path.stat().st_size
        log_extra = _log_extra(source_name=source_name, file_size=file_size)

        self.stdout.write(f"Starting EPUB import: {source_name}")
        logger.info(
            _operator_epub_log_message(
                event="started",
                source_name=source_name,
                status="started",
            ),
            extra={**log_extra, "status": "started"},
        )

        if file_size > MAX_SINGLE_EPUB_UPLOAD_BYTES:
            warning = (
                "Local EPUB exceeds the normal Product/API "
                f"{_format_mib(MAX_SINGLE_EPUB_UPLOAD_BYTES)} single-upload limit; "
                "continuing because this is an operator import."
            )
            self.stderr.write(self.style.WARNING(warning))
            logger.warning(
                _operator_epub_log_message(
                    event="size_warning",
                    source_name=source_name,
                    status="size_warning",
                    safe_message=warning,
                ),
                extra={
                    **log_extra,
                    "status": "size_warning",
                    "limit_bytes": MAX_SINGLE_EPUB_UPLOAD_BYTES,
                },
            )

        try:
            result = import_epub(file_path)
            book_title = result.book.title if result.book is not None else file_path
            if result.status == ImportStatus.DUPLICATE:
                message = f"EPUB already exists: {book_title}"
                self.stdout.write(self.style.WARNING(message))
                logger.info(
                    _operator_epub_log_message(
                        event="duplicate",
                        source_name=source_name,
                        status="duplicate",
                    ),
                    extra={**log_extra, "status": "duplicate", "checksum": result.checksum},
                )
            elif result.status == ImportStatus.IMPORTED:
                message = f"Successfully imported EPUB: {book_title}"
                self.stdout.write(self.style.SUCCESS(message))
                logger.info(
                    _operator_epub_log_message(
                        event="succeeded",
                        source_name=source_name,
                        status="imported",
                    ),
                    extra={**log_extra, "status": "imported", "checksum": result.checksum},
                )
            else:
                safe_message = sanitize_import_error_message(result.message or "Unknown error")
                self.stderr.write(self.style.ERROR(f"Failed to import EPUB: {safe_message}"))
                logger.warning(
                    _operator_epub_log_message(
                        event="failed",
                        source_name=source_name,
                        status="failed",
                        safe_message=safe_message,
                    ),
                    extra={**log_extra, "status": "failed", "safe_message": safe_message},
                )
                raise CommandError(safe_message)
        except CommandError:
            raise
        except ValueError as e:
            safe_message = sanitize_import_error_message(e)
            self.stderr.write(self.style.ERROR(f"Failed to import EPUB: {safe_message}"))
            logger.warning(
                _operator_epub_log_message(
                    event="failed",
                    source_name=source_name,
                    status="failed",
                    safe_message=safe_message,
                ),
                extra={
                    **log_extra,
                    "status": "failed",
                    "safe_message": safe_message,
                    "exception_class": e.__class__.__name__,
                },
            )
            raise CommandError(safe_message)
        except Exception as e:
            safe_message = sanitize_import_error_message(e)
            self.stderr.write(self.style.ERROR(f"Failed to import EPUB: {safe_message}"))
            logger.error(
                _operator_epub_log_message(
                    event="failed_unexpectedly",
                    source_name=source_name,
                    status="failed",
                    safe_message=safe_message,
                ),
                extra={
                    **log_extra,
                    "status": "failed",
                    "safe_message": safe_message,
                    "exception_class": e.__class__.__name__,
                },
                exc_info=True,
            )
            raise CommandError(safe_message)
