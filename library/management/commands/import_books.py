from __future__ import annotations

import logging
from pathlib import Path
import uuid

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from library.cover_services import MAX_COVER_BYTES
from library.imports.archives import process_zip_import_path, safe_import_source_name
from library.imports.epub import import_epub
from library.imports.opf import MAX_OPF_SIDECAR_XML_BYTES
from library.imports.upload import (
    MAX_ZIP_EPUB_MEMBER_BYTES,
    MAX_ZIP_MEMBERS,
    MAX_ZIP_TOTAL_EPUB_BYTES,
    MAX_ZIP_UPLOAD_BYTES,
    ImportResourceLimitError,
    ImportResultStatus,
    ImportRunItem,
    ImportRunResult,
    ImportSourceType,
    sanitize_import_error_message,
)


logger = logging.getLogger(__name__)


def _imports_dir() -> Path:
    return Path(getattr(settings, "IMPORTS_DIR", getattr(settings, "USERDATA_DIR")))


def _format_mib(byte_count: int) -> str:
    return f"{byte_count // (1024 * 1024)} MiB"


def _log_extra(
    *,
    result: ImportRunResult | None = None,
    source_name: str | None = None,
    file_size: int | None = None,
    status: str | None = None,
    safe_message: str | None = None,
    item_source_name: str | None = None,
    exception_class: str | None = None,
) -> dict[str, object]:
    extra: dict[str, object] = {}
    if result is not None:
        extra.update(
            {
                "run_id": result.run_id,
                "source_type": result.source_type,
                "source_name": safe_import_source_name(result.source_filename),
                "status": result.status,
                "total_found": result.total_found,
                "imported_count": result.imported_count,
                "duplicate_count": result.duplicate_count,
                "failed_count": result.failed_count,
            }
        )
    if source_name is not None:
        extra["source_name"] = safe_import_source_name(source_name)
    if file_size is not None:
        extra["file_size"] = file_size
    if status is not None:
        extra["status"] = status
    if safe_message is not None:
        extra["safe_message"] = safe_message
    if item_source_name is not None:
        extra["item_source_name"] = safe_import_source_name(item_source_name)
    if exception_class is not None:
        extra["exception_class"] = exception_class
    return extra


def _log_item_failure(
    *, result: ImportRunResult, item_source_name: str, safe_message: str
) -> None:
    logger.warning(
        "operator zip import item failed",
        extra=_log_extra(
            result=result,
            item_source_name=item_source_name,
            safe_message=safe_message,
        ),
    )


def _log_archive_rejected(*, result: ImportRunResult, safe_message: str) -> None:
    logger.warning(
        "operator zip import failed",
        extra=_log_extra(result=result, status=ImportResultStatus.FAILED, safe_message=safe_message),
    )


class Command(BaseCommand):
    help = "Operator-only import for one local ZIP archive of EPUB files"

    def add_arguments(self, parser):
        parser.add_argument("file_path", type=str, help="Path to the ZIP archive")

    def handle(self, *args, **options):
        file_path = options["file_path"]
        path = Path(file_path)
        source_name = path.name or file_path

        if not path.exists():
            message = f"File does not exist: {file_path}"
            self.stderr.write(self.style.ERROR(f"Failed to import ZIP: {message}"))
            logger.warning(
                "operator zip import failed",
                extra=_log_extra(
                    source_name=source_name,
                    status=ImportResultStatus.FAILED,
                    safe_message=message,
                ),
            )
            raise CommandError(message)

        if path.suffix.lower() != ".zip":
            message = f"File must have .zip extension: {file_path}"
            file_size = path.stat().st_size
            self.stderr.write(self.style.ERROR(f"Failed to import ZIP: {message}"))
            logger.warning(
                "operator zip import failed",
                extra=_log_extra(
                    source_name=source_name,
                    file_size=file_size,
                    status=ImportResultStatus.FAILED,
                    safe_message=message,
                ),
            )
            raise CommandError(message)

        file_size = path.stat().st_size
        if file_size > MAX_ZIP_UPLOAD_BYTES:
            message = f"ZIP archive exceeds the {_format_mib(MAX_ZIP_UPLOAD_BYTES)} limit."
            self.stderr.write(self.style.ERROR(f"Failed to import ZIP: {message}"))
            logger.warning(
                "operator zip import failed",
                extra=_log_extra(
                    source_name=source_name,
                    file_size=file_size,
                    status=ImportResultStatus.FAILED,
                    safe_message=message,
                ),
            )
            raise CommandError(message)

        result = ImportRunResult(
            run_id=str(uuid.uuid4()),
            status=ImportResultStatus.COMPLETED,
            source_type=ImportSourceType.ZIP,
            source_filename=source_name,
        )
        run_dir = _imports_dir() / "jobs" / result.run_id
        extraction_dir = run_dir / "extracted"

        self.stdout.write(f"Starting ZIP book import: {safe_import_source_name(source_name)}")
        logger.info(
            "operator zip import started",
            extra=_log_extra(result=result, file_size=file_size, status="started"),
        )

        try:
            result = process_zip_import_path(
                result=result,
                zip_path=path,
                extraction_dir=extraction_dir,
                import_epub_func=import_epub,
                max_opf_xml_bytes=MAX_OPF_SIDECAR_XML_BYTES,
                max_cover_bytes=MAX_COVER_BYTES,
                import_run_item_factory=ImportRunItem,
                resource_limit_error_class=ImportResourceLimitError,
                sanitize_error_message=sanitize_import_error_message,
                log_item_failure=_log_item_failure,
                log_archive_rejected=_log_archive_rejected,
                max_zip_members=MAX_ZIP_MEMBERS,
                max_zip_epub_member_bytes=MAX_ZIP_EPUB_MEMBER_BYTES,
                max_zip_total_epub_bytes=MAX_ZIP_TOTAL_EPUB_BYTES,
            )
        except CommandError:
            raise
        except ImportResourceLimitError as exc:
            safe_message = str(exc)
            self.stderr.write(self.style.ERROR(f"Failed to import ZIP: {safe_message}"))
            raise CommandError(safe_message)
        except Exception as exc:
            safe_message = sanitize_import_error_message(exc)
            self.stderr.write(self.style.ERROR(f"Failed to import ZIP: {safe_message}"))
            logger.error(
                "operator zip import failed",
                extra=_log_extra(
                    result=result,
                    status=ImportResultStatus.FAILED,
                    safe_message=safe_message,
                    exception_class=exc.__class__.__name__,
                ),
            )
            raise CommandError(safe_message)
        finally:
            try:
                run_dir.rmdir()
            except OSError:
                pass

        self.stdout.write(f"Found: {result.total_found}")
        self.stdout.write(f"Imported: {result.imported_count}")
        self.stdout.write(f"Duplicates: {result.duplicate_count}")
        self.stdout.write(f"Failed: {result.failed_count}")

        for item in result.items:
            if item.status == "failed":
                self.stderr.write(
                    self.style.ERROR(f"Failed item {item.source_name}: {item.message}")
                )

        if result.status == ImportResultStatus.COMPLETED:
            self.stdout.write(self.style.SUCCESS("ZIP import completed."))
            logger.info(
                "operator zip import succeeded",
                extra=_log_extra(result=result, status=result.status),
            )
        else:
            self.stdout.write(self.style.WARNING("ZIP import completed with failures."))
            logger.warning(
                "operator zip import completed with failures",
                extra=_log_extra(result=result, status=result.status),
            )
