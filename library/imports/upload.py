from __future__ import annotations

from dataclasses import dataclass, field
import logging
from pathlib import Path, PurePath
import posixpath
import uuid
import zipfile
from typing import BinaryIO, Callable

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile


MAX_SINGLE_EPUB_UPLOAD_BYTES = 200 * 1024 * 1024
MAX_ZIP_UPLOAD_BYTES = 1024 * 1024 * 1024
MAX_ZIP_MEMBERS = 5000
MAX_ZIP_EPUB_MEMBER_BYTES = 200 * 1024 * 1024
MAX_ZIP_TOTAL_EPUB_BYTES = 2 * 1024 * 1024 * 1024
COPY_CHUNK_BYTES = 1024 * 1024

logger = logging.getLogger(__name__)


class ImportResourceLimitError(ValueError):
    pass


class ImportResultStatus:
    COMPLETED = "completed"
    FAILED = "failed"


class ImportSourceType:
    EPUB = "epub"
    ZIP = "zip"


class ImportItemStatus:
    IMPORTED = "imported"
    DUPLICATE = "duplicate"
    FAILED = "failed"


@dataclass
class ImportRunItem:
    status: str
    source_name: str = ""
    book: object | None = None
    book_file: object | None = None
    message: str = ""

    def as_dict(self) -> dict[str, object | None]:
        return {
            "status": self.status,
            "source_name": self.source_name,
            "book": str(getattr(self.book, "id", "")) if self.book is not None else None,
            "book_file": str(getattr(self.book_file, "id", ""))
            if self.book_file is not None
            else None,
            "message": self.message,
        }


@dataclass
class ImportRunResult:
    run_id: str
    status: str
    source_type: str
    source_filename: str
    total_found: int = 0
    imported_count: int = 0
    duplicate_count: int = 0
    failed_count: int = 0
    message: str = ""
    items: list[ImportRunItem] = field(default_factory=list)

    def finalize_counts(self) -> None:
        self.imported_count = sum(
            1 for item in self.items if item.status == ImportItemStatus.IMPORTED
        )
        self.duplicate_count = sum(
            1 for item in self.items if item.status == ImportItemStatus.DUPLICATE
        )
        self.failed_count = sum(
            1 for item in self.items if item.status == ImportItemStatus.FAILED
        )
        self.status = (
            ImportResultStatus.COMPLETED
            if self.failed_count == 0
            else ImportResultStatus.FAILED
        )
        self.message = (
            "Import completed."
            if self.status == ImportResultStatus.COMPLETED
            else "Import completed with failures."
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "status": self.status,
            "source_type": self.source_type,
            "source_filename": self.source_filename,
            "total_found": self.total_found,
            "imported_count": self.imported_count,
            "duplicate_count": self.duplicate_count,
            "failed_count": self.failed_count,
            "message": self.message,
            "items": [item.as_dict() for item in self.items],
        }


def sanitize_import_error_message(exc_or_message: object) -> str:
    if isinstance(exc_or_message, ImportResourceLimitError):
        return str(exc_or_message)

    raw = str(exc_or_message or "").lower()
    if "zip" in raw:
        return "Invalid or unsupported EPUB/ZIP structure."
    if "epub" in raw:
        return "Invalid or unsupported EPUB file."
    if "xml" in raw or "opf" in raw:
        return "Invalid or unsupported EPUB metadata."
    if "image" in raw or "cover" in raw:
        return "Invalid or unsupported cover image."
    if isinstance(exc_or_message, (OSError, ValueError)):
        return "Invalid or unsupported EPUB file."
    return "Unexpected import failure."


def _safe_import_result_message(*, status: str, message: object) -> str:
    if status in {ImportItemStatus.IMPORTED, ImportItemStatus.DUPLICATE}:
        return str(message or "")
    return sanitize_import_error_message(message)


def _safe_import_source_name(source_name: str) -> str:
    return PurePath((source_name or "").replace("\\", "/")).name


def _log_extra(
    *,
    run_id: str | None = None,
    source_type: str | None = None,
    source_name: str | None = None,
    status: str | None = None,
    safe_message: str | None = None,
    item_status: str | None = None,
    item_source_name: str | None = None,
    exception_class: str | None = None,
    result: "ImportRunResult | None" = None,
) -> dict[str, object]:
    extra: dict[str, object] = {}
    if result is not None:
        extra.update(
            {
                "run_id": result.run_id,
                "source_type": result.source_type,
                "source_name": _safe_import_source_name(result.source_filename),
                "status": result.status,
                "total_found": result.total_found,
                "imported_count": result.imported_count,
                "duplicate_count": result.duplicate_count,
                "failed_count": result.failed_count,
            }
        )
    if run_id is not None:
        extra["run_id"] = run_id
    if source_type is not None:
        extra["source_type"] = source_type
    if source_name is not None:
        extra["source_name"] = _safe_import_source_name(source_name)
    if status is not None:
        extra["status"] = status
    if safe_message is not None:
        extra["safe_message"] = safe_message
    if item_status is not None:
        extra["item_status"] = item_status
    if item_source_name is not None:
        extra["item_source_name"] = _safe_import_source_name(item_source_name)
    if exception_class is not None:
        extra["exception_class"] = exception_class
    return extra


def _imports_dir() -> Path:
    return Path(getattr(settings, "IMPORTS_DIR", getattr(settings, "USERDATA_DIR")))  # type: ignore[arg-type]


def _format_mib(byte_count: int) -> str:
    return f"{byte_count // (1024 * 1024)} MiB"


def _uploaded_size(uploaded_file: UploadedFile) -> int | None:
    size = getattr(uploaded_file, "size", None)
    return size if isinstance(size, int) else None


def _max_upload_bytes_for_source(source_type: str) -> int:
    if source_type == ImportSourceType.ZIP:
        return MAX_ZIP_UPLOAD_BYTES
    return MAX_SINGLE_EPUB_UPLOAD_BYTES


def _validate_uploaded_size(*, uploaded_file: UploadedFile, source_type: str) -> None:
    size = _uploaded_size(uploaded_file)
    max_bytes = _max_upload_bytes_for_source(source_type)
    if size is not None and size > max_bytes:
        label = "ZIP" if source_type == ImportSourceType.ZIP else "EPUB"
        message = f"{label} upload exceeds the {_format_mib(max_bytes)} limit."
        logger.warning(
            "library import upload rejected by size limit",
            extra=_log_extra(
                source_type=source_type,
                source_name=getattr(uploaded_file, "name", ""),
                status=ImportResultStatus.FAILED,
                safe_message=message,
            ),
        )
        raise ImportResourceLimitError(message)


def _copy_fileobj_capped(*, src: BinaryIO, dst_path: Path, max_bytes: int) -> int:
    written = 0
    try:
        with dst_path.open("wb") as dst:
            while True:
                chunk = src.read(COPY_CHUNK_BYTES)
                if not chunk:
                    break
                written += len(chunk)
                if written > max_bytes:
                    raise ImportResourceLimitError(
                        f"EPUB member exceeds the {_format_mib(max_bytes)} uncompressed limit."
                    )
                dst.write(chunk)
    except Exception:
        dst_path.unlink(missing_ok=True)
        raise
    return written


def _stage_uploaded_file(
    *, uploaded_file: UploadedFile, run_id: str, source_type: str
) -> tuple[str, Path]:
    imports_dir = _imports_dir()
    run_dir = imports_dir / "jobs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    extension = ".zip" if source_type == ImportSourceType.ZIP else ".epub"
    staged_name = f"{uuid.uuid4().hex}{extension}"
    staged_path = run_dir / staged_name

    max_bytes = _max_upload_bytes_for_source(source_type)
    written = 0
    try:
        with staged_path.open("wb") as out:
            for chunk in uploaded_file.chunks():
                written += len(chunk)
                if written > max_bytes:
                    label = "ZIP" if source_type == ImportSourceType.ZIP else "EPUB"
                    message = f"{label} upload exceeds the {_format_mib(max_bytes)} limit."
                    logger.warning(
                        "library import upload rejected by streaming size limit",
                        extra=_log_extra(
                            run_id=run_id,
                            source_type=source_type,
                            source_name=getattr(uploaded_file, "name", ""),
                            status=ImportResultStatus.FAILED,
                            safe_message=message,
                        ),
                    )
                    raise ImportResourceLimitError(message)
                out.write(chunk)
    except Exception:
        staged_path.unlink(missing_ok=True)
        raise

    staged_rel = str(Path("jobs") / run_id / staged_name)
    return staged_rel, staged_path


def create_import_result_from_upload(
    *,
    user,
    uploaded_file: UploadedFile,
    import_epub_func: Callable[..., object],
    max_opf_xml_bytes: int,
    max_cover_bytes: int,
) -> ImportRunResult:
    name = (uploaded_file.name or "").strip()
    lower = name.lower()
    if lower.endswith(".epub"):
        source_type = ImportSourceType.EPUB
    elif lower.endswith(".zip"):
        source_type = ImportSourceType.ZIP
    else:
        logger.warning(
            "library import upload rejected by type",
            extra=_log_extra(
                source_name=name,
                status=ImportResultStatus.FAILED,
                safe_message="Upload must be a .epub or .zip file.",
            ),
        )
        raise ValueError("Upload must be a .epub or .zip file.")

    _validate_uploaded_size(uploaded_file=uploaded_file, source_type=source_type)

    run_id = str(uuid.uuid4())
    staged_rel, _staged_path = _stage_uploaded_file(
        uploaded_file=uploaded_file, run_id=run_id, source_type=source_type
    )
    result = ImportRunResult(
        run_id=run_id,
        status=ImportResultStatus.COMPLETED,
        source_type=source_type,
        source_filename=name,
    )
    logger.info(
        "library import started",
        extra=_log_extra(result=result),
    )
    try:
        return process_import_result(
            result=result,
            staged_rel=staged_rel,
            import_epub_func=import_epub_func,
            max_opf_xml_bytes=max_opf_xml_bytes,
            max_cover_bytes=max_cover_bytes,
        )
    except ImportResourceLimitError:
        raise
    except Exception as exc:
        logger.error(
            "library import failed unexpectedly",
            extra=_log_extra(
                result=result,
                status=ImportResultStatus.FAILED,
                exception_class=exc.__class__.__name__,
            ),
            exc_info=True,
        )
        raise


def _safe_zip_member_name(name: str) -> str | None:
    if not name:
        return None
    if name.startswith(("/", "\\")) or ":" in name:
        return None
    name = name.replace("\\", "/")

    # Normalize harmless "./" segments so directory matching (e.g. metadata.opf)
    # remains stable across ZIP tools.
    parts = [p for p in name.split("/") if p != "."]
    if any(p in {"", ".."} for p in parts):
        return None
    normalized = "/".join(parts)
    if not normalized:
        return None
    if normalized.startswith("/"):
        return None
    if normalized.startswith("../") or normalized == "..":
        return None
    return normalized


def _zip_sidecar_opf_for_epub(
    *,
    epub_member: str,
    opfs_by_dir: dict[str, list[str]],
    members_index: dict[str, zipfile.ZipInfo],
) -> str | None:
    epub_member = epub_member.replace("\\", "/")
    d = posixpath.dirname(epub_member)
    base = posixpath.basename(epub_member)
    stem, _ext = posixpath.splitext(base)

    preferred = posixpath.join(d, "metadata.opf") if d else "metadata.opf"
    if preferred in members_index:
        return preferred

    same_base = posixpath.join(d, f"{stem}.opf") if d else f"{stem}.opf"
    if same_base in members_index:
        return same_base

    opfs = opfs_by_dir.get(d or "", [])
    if len(opfs) == 1:
        return opfs[0]

    return None


def process_import_result(
    *,
    result: ImportRunResult,
    staged_rel: str,
    import_epub_func: Callable[..., object],
    max_opf_xml_bytes: int,
    max_cover_bytes: int,
) -> ImportRunResult:
    staged_rel = (staged_rel or "").strip()
    if not staged_rel:
        result.status = ImportResultStatus.FAILED
        result.message = "Missing staged upload."
        return result

    imports_dir = _imports_dir()
    staged_path = imports_dir / staged_rel
    if not staged_path.exists():
        result.status = ImportResultStatus.FAILED
        result.message = "Staged upload missing on disk."
        return result

    extracted_dir: Path | None = None
    try:
        if result.source_type == ImportSourceType.EPUB:
            result.total_found = 1
            try:
                import_result = import_epub_func(str(staged_path))
                status_val = getattr(import_result, "status", None)
                item_status = (
                    ImportItemStatus.IMPORTED
                    if status_val == "imported"
                    else ImportItemStatus.DUPLICATE
                    if status_val == "duplicate"
                    else ImportItemStatus.FAILED
                )
                result_message = getattr(import_result, "message", "") or ""
                item = ImportRunItem(
                    status=item_status,
                    source_name=_safe_import_source_name(result.source_filename or ""),
                    book=getattr(import_result, "book", None),
                    book_file=getattr(import_result, "book_file", None),
                    message=_safe_import_result_message(
                        status=item_status,
                        message=result_message,
                    ),
                )
            except Exception as e:
                safe_message = sanitize_import_error_message(e)
                logger.warning(
                    "library import item failed",
                    extra=_log_extra(
                        result=result,
                        item_status=ImportItemStatus.FAILED,
                        item_source_name=result.source_filename,
                        safe_message=safe_message,
                    ),
                )
                item = ImportRunItem(
                    status=ImportItemStatus.FAILED,
                    source_name=_safe_import_source_name(result.source_filename or ""),
                    message=safe_message,
                )
            result.items.append(item)
        else:
            extracted_dir = imports_dir / "jobs" / result.run_id / "extracted"
            extracted_dir.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(staged_path, "r") as zf:
                all_infos = zf.infolist()
                if len(all_infos) > MAX_ZIP_MEMBERS:
                    message = f"ZIP contains more than {MAX_ZIP_MEMBERS} entries."
                    logger.warning(
                        "library import rejected by zip member count limit",
                        extra=_log_extra(result=result, safe_message=message),
                    )
                    raise ImportResourceLimitError(message)

                members_index: dict[str, zipfile.ZipInfo] = {}
                epub_members: list[zipfile.ZipInfo] = []
                opfs_by_dir: dict[str, list[str]] = {}
                collisions: set[str] = set()

                for info in all_infos:
                    if info.is_dir():
                        continue
                    safe_name = _safe_zip_member_name(info.filename)
                    if safe_name is None:
                        continue
                    if safe_name in members_index:
                        collisions.add(safe_name)
                        continue
                    info.filename = safe_name
                    members_index[safe_name] = info

                    lower = safe_name.lower()
                    if lower.endswith(".epub"):
                        epub_members.append(info)
                    elif lower.endswith(".opf"):
                        d = posixpath.dirname(safe_name)
                        opfs_by_dir.setdefault(d, []).append(safe_name)

                if collisions:
                    members_index = {
                        k: v for (k, v) in members_index.items() if k not in collisions
                    }
                    epub_members = [
                        i for i in epub_members if i.filename not in collisions
                    ]
                    for d, names in list(opfs_by_dir.items()):
                        filtered = [n for n in names if n not in collisions]
                        if filtered:
                            opfs_by_dir[d] = filtered
                        else:
                            opfs_by_dir.pop(d, None)

                members = epub_members
                result.total_found = len(members)

                copied_epub_bytes = 0
                for info in members:
                    source_name = info.filename
                    safe_source_name = _safe_import_source_name(source_name)
                    try:
                        if info.file_size > MAX_ZIP_EPUB_MEMBER_BYTES:
                            raise ImportResourceLimitError(
                                "EPUB member exceeds the "
                                f"{_format_mib(MAX_ZIP_EPUB_MEMBER_BYTES)} uncompressed limit."
                            )
                        if copied_epub_bytes + info.file_size > MAX_ZIP_TOTAL_EPUB_BYTES:
                            raise ImportResourceLimitError(
                                "ZIP EPUB contents exceed the "
                                f"{_format_mib(MAX_ZIP_TOTAL_EPUB_BYTES)} total uncompressed limit."
                            )

                        extracted_name = f"{uuid.uuid4().hex}.epub"
                        extracted_path = extracted_dir / extracted_name
                        with zf.open(info, "r") as src:
                            written = _copy_fileobj_capped(
                                src=src,
                                dst_path=extracted_path,
                                max_bytes=MAX_ZIP_EPUB_MEMBER_BYTES,
                            )
                        if copied_epub_bytes + written > MAX_ZIP_TOTAL_EPUB_BYTES:
                            extracted_path.unlink(missing_ok=True)
                            raise ImportResourceLimitError(
                                "ZIP EPUB contents exceed the "
                                f"{_format_mib(MAX_ZIP_TOTAL_EPUB_BYTES)} total uncompressed limit."
                            )
                        copied_epub_bytes += written

                        sidecar_opf_member = _zip_sidecar_opf_for_epub(
                            epub_member=source_name,
                            opfs_by_dir=opfs_by_dir,
                            members_index=members_index,
                        )
                        sidecar_opf_bytes: bytes | None = None
                        sidecar_opf_dir: str | None = None
                        if sidecar_opf_member is not None:
                            try:
                                with zf.open(sidecar_opf_member, "r") as opf_fp:
                                    sidecar_opf_bytes = opf_fp.read(max_opf_xml_bytes + 1)
                                if (
                                    sidecar_opf_bytes
                                    and len(sidecar_opf_bytes) > max_opf_xml_bytes
                                ):
                                    sidecar_opf_bytes = None
                                else:
                                    sidecar_opf_dir = posixpath.dirname(sidecar_opf_member)
                            except Exception:
                                sidecar_opf_bytes = None
                                sidecar_opf_dir = None

                        def asset_reader(member: str) -> bytes | None:
                            safe = _safe_zip_member_name(member)
                            if safe is None:
                                return None
                            if safe in collisions:
                                return None
                            if safe not in members_index:
                                return None
                            try:
                                with zf.open(safe, "r") as fp:
                                    data = fp.read(max_cover_bytes + 1)
                                if len(data) > max_cover_bytes:
                                    return None
                                return data
                            except Exception:
                                return None

                        import_result = import_epub_func(
                            str(extracted_path),
                            sidecar_opf_bytes=sidecar_opf_bytes,
                            sidecar_opf_dir=sidecar_opf_dir,
                            sidecar_asset_reader=(
                                asset_reader
                                if sidecar_opf_bytes and sidecar_opf_dir
                                else None
                            ),
                        )

                        status_val = getattr(import_result, "status", None)
                        item_status = (
                            ImportItemStatus.IMPORTED
                            if status_val == "imported"
                            else ImportItemStatus.DUPLICATE
                            if status_val == "duplicate"
                            else ImportItemStatus.FAILED
                        )
                        result.items.append(
                            ImportRunItem(
                                status=item_status,
                                source_name=safe_source_name,
                                book=getattr(import_result, "book", None),
                                book_file=getattr(import_result, "book_file", None),
                                message=_safe_import_result_message(
                                    status=item_status,
                                    message=getattr(import_result, "message", "") or "",
                                ),
                            )
                        )
                    except Exception as e:
                        safe_message = sanitize_import_error_message(e)
                        logger.warning(
                            "library import item failed",
                            extra=_log_extra(
                                result=result,
                                item_status=ImportItemStatus.FAILED,
                                item_source_name=safe_source_name,
                                safe_message=safe_message,
                            ),
                        )
                        result.items.append(
                            ImportRunItem(
                                status=ImportItemStatus.FAILED,
                                source_name=safe_source_name,
                                message=safe_message,
                            )
                        )
                        continue

        result.finalize_counts()
        logger.info(
            "library import finished",
            extra=_log_extra(result=result),
        )
        return result
    finally:
        if extracted_dir is not None and extracted_dir.exists():
            for child in extracted_dir.iterdir():
                if child.is_file():
                    child.unlink(missing_ok=True)
            try:
                extracted_dir.rmdir()
            except OSError:
                pass
        staged_path.unlink(missing_ok=True)
        try:
            staged_path.parent.rmdir()
        except OSError:
            pass
