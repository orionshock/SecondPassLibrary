from __future__ import annotations

from dataclasses import dataclass, field
import logging
from pathlib import Path, PurePath
import posixpath
import uuid
import zipfile
from typing import BinaryIO, Callable, Protocol, TypeVar


MAX_ZIP_UPLOAD_BYTES = 1024 * 1024 * 1024
MAX_ZIP_MEMBERS = 5000
MAX_ZIP_EPUB_MEMBER_BYTES = 200 * 1024 * 1024
MAX_ZIP_TOTAL_EPUB_BYTES = 2 * 1024 * 1024 * 1024
COPY_CHUNK_BYTES = 1024 * 1024

IMPORT_RESULT_STATUS_MAP = {
    "imported": "imported",
    "duplicate": "duplicate",
}

logger = logging.getLogger(__name__)


class ImportRunResultLike(Protocol):
    total_found: int
    items: list[object]

    def finalize_counts(self) -> None: ...


ResultT = TypeVar("ResultT", bound=ImportRunResultLike)


@dataclass(frozen=True)
class ZipMember:
    safe_name: str
    info: zipfile.ZipInfo

    @property
    def source_name(self) -> str:
        return self.safe_name

    @property
    def safe_source_name(self) -> str:
        return safe_import_source_name(self.safe_name)


@dataclass
class ZipIndex:
    members_index: dict[str, ZipMember] = field(default_factory=dict)
    epub_members: list[ZipMember] = field(default_factory=list)
    opfs_by_dir: dict[str, list[str]] = field(default_factory=dict)
    collisions: set[str] = field(default_factory=set)

    def without_collisions(self) -> "ZipIndex":
        if not self.collisions:
            return self

        # If two entries normalize to the same safe name, all colliding entries
        # are ignored. Guessing would make sidecar matching and extraction unsafe.
        members_index = {
            name: member
            for name, member in self.members_index.items()
            if name not in self.collisions
        }
        epub_members = [
            member for member in self.epub_members if member.safe_name not in self.collisions
        ]
        opfs_by_dir: dict[str, list[str]] = {}
        for directory, names in self.opfs_by_dir.items():
            filtered = [name for name in names if name not in self.collisions]
            if filtered:
                opfs_by_dir[directory] = filtered

        return ZipIndex(
            members_index=members_index,
            epub_members=epub_members,
            opfs_by_dir=opfs_by_dir,
            collisions=set(self.collisions),
        )


@dataclass(frozen=True)
class SidecarOpf:
    member_name: str
    directory: str
    data: bytes


@dataclass
class ZipImportContext:
    zf: zipfile.ZipFile
    index: ZipIndex
    extraction_dir: Path
    import_epub_func: Callable[..., object]
    import_run_item_factory: Callable[..., object]
    resource_limit_error_class: type[Exception]
    sanitize_error_message: Callable[[object], str]
    log_item_failure: Callable[..., None]
    max_opf_xml_bytes: int
    max_cover_bytes: int
    max_zip_epub_member_bytes: int
    max_zip_total_epub_bytes: int
    copied_epub_bytes: int = 0


def format_mib(byte_count: int) -> str:
    return f"{byte_count // (1024 * 1024)} MiB"


def safe_import_source_name(source_name: str) -> str:
    return PurePath((source_name or "").replace("\\", "/")).name


def safe_zip_member_name(name: str) -> str | None:
    if not name:
        return None
    if name.startswith(("/", "\\")) or ":" in name:
        return None
    name = name.replace("\\", "/")

    # Normalize harmless "./" segments while still rejecting empty path
    # segments and traversal. ZIP input is untrusted even for operator paths.
    parts = [p for p in name.split("/") if p != "."]
    if any(p in {"", ".."} for p in parts):
        return None
    normalized = "/".join(parts)
    if not normalized:
        return None
    if normalized.startswith("/") or normalized.startswith("../") or normalized == "..":
        return None
    return normalized


def zip_sidecar_opf_for_epub(
    *,
    epub_member: str,
    opfs_by_dir: dict[str, list[str]],
    members_index: dict[str, ZipMember],
) -> str | None:
    epub_member = epub_member.replace("\\", "/")
    directory = posixpath.dirname(epub_member)
    base = posixpath.basename(epub_member)
    stem, _ext = posixpath.splitext(base)

    preferred = posixpath.join(directory, "metadata.opf") if directory else "metadata.opf"
    if preferred in members_index:
        return preferred

    same_base = posixpath.join(directory, f"{stem}.opf") if directory else f"{stem}.opf"
    if same_base in members_index:
        return same_base

    opfs = opfs_by_dir.get(directory or "", [])
    if len(opfs) == 1:
        return opfs[0]

    return None


def copy_fileobj_capped(*, src: BinaryIO, dst_path: Path, max_bytes: int) -> int:
    written = 0
    try:
        with dst_path.open("wb") as dst:
            while True:
                chunk = src.read(COPY_CHUNK_BYTES)
                if not chunk:
                    break
                written += len(chunk)
                if written > max_bytes:
                    raise ValueError(
                        f"EPUB member exceeds the {format_mib(max_bytes)} uncompressed limit."
                    )
                dst.write(chunk)
    except Exception:
        dst_path.unlink(missing_ok=True)
        raise
    return written


def build_zip_index(infos: list[zipfile.ZipInfo]) -> ZipIndex:
    index = ZipIndex()
    for info in infos:
        if info.is_dir():
            continue
        safe_name = safe_zip_member_name(info.filename)
        if safe_name is None:
            continue
        if safe_name in index.members_index:
            index.collisions.add(safe_name)
            continue

        member = ZipMember(safe_name=safe_name, info=info)
        index.members_index[safe_name] = member

        lower = safe_name.lower()
        if lower.endswith(".epub"):
            index.epub_members.append(member)
        elif lower.endswith(".opf"):
            directory = posixpath.dirname(safe_name)
            index.opfs_by_dir.setdefault(directory, []).append(safe_name)

    return index.without_collisions()


def read_sidecar_opf(
    *,
    zf: zipfile.ZipFile,
    member_name: str | None,
    members_index: dict[str, ZipMember],
    max_opf_xml_bytes: int,
) -> SidecarOpf | None:
    if member_name is None:
        return None

    member = members_index.get(member_name)
    if member is None:
        return None

    try:
        with zf.open(member.info, "r") as opf_fp:
            data = opf_fp.read(max_opf_xml_bytes + 1)
        if data and len(data) <= max_opf_xml_bytes:
            return SidecarOpf(
                member_name=member.safe_name,
                directory=posixpath.dirname(member.safe_name),
                data=data,
            )
    except Exception as exc:
        logger.debug(
            "zip sidecar opf read ignored",
            extra={
                "item_source_name": safe_import_source_name(member.safe_name),
                "exception_class": exc.__class__.__name__,
            },
        )
    return None


def make_sidecar_asset_reader(
    *,
    zf: zipfile.ZipFile,
    members_index: dict[str, ZipMember],
    collisions: set[str],
    max_cover_bytes: int,
) -> Callable[[str], bytes | None]:
    def asset_reader(member_name: str) -> bytes | None:
        safe = safe_zip_member_name(member_name)
        if safe is None or safe in collisions:
            return None
        member = members_index.get(safe)
        if member is None:
            return None
        try:
            with zf.open(member.info, "r") as fp:
                data = fp.read(max_cover_bytes + 1)
            if len(data) > max_cover_bytes:
                return None
            return data
        except Exception as exc:
            logger.debug(
                "zip sidecar asset read ignored",
                extra={
                    "item_source_name": safe_import_source_name(safe),
                    "exception_class": exc.__class__.__name__,
                },
            )
            return None

    return asset_reader


def run_item_from_import_result(
    *,
    import_result: object,
    source_name: str,
    import_run_item_factory: Callable[..., object],
    sanitize_error_message: Callable[[object], str],
) -> object:
    status_val = getattr(import_result, "status", None)
    status_key = getattr(status_val, "value", status_val)
    item_status = IMPORT_RESULT_STATUS_MAP.get(status_key, "failed")
    message = getattr(import_result, "message", "") or ""
    if item_status == "failed":
        message = sanitize_error_message(message)

    return import_run_item_factory(
        status=item_status,
        source_name=source_name,
        book=getattr(import_result, "book", None),
        book_file=getattr(import_result, "book_file", None),
        message=str(message or ""),
    )


def failed_run_item(
    *,
    source_name: str,
    message: str,
    import_run_item_factory: Callable[..., object],
) -> object:
    return import_run_item_factory(
        status="failed",
        source_name=source_name,
        message=message,
    )


def enforce_member_size_limits(*, context: ZipImportContext, member: ZipMember) -> None:
    if member.info.file_size > context.max_zip_epub_member_bytes:
        raise context.resource_limit_error_class(
            "EPUB member exceeds the "
            f"{format_mib(context.max_zip_epub_member_bytes)} uncompressed limit."
        )
    if context.copied_epub_bytes + member.info.file_size > context.max_zip_total_epub_bytes:
        raise context.resource_limit_error_class(
            "ZIP EPUB contents exceed the "
            f"{format_mib(context.max_zip_total_epub_bytes)} total uncompressed limit."
        )


def extract_epub_member(*, context: ZipImportContext, member: ZipMember) -> Path:
    extracted_path = context.extraction_dir / f"{uuid.uuid4().hex}.epub"
    with context.zf.open(member.info, "r") as src:
        try:
            written = copy_fileobj_capped(
                src=src,
                dst_path=extracted_path,
                max_bytes=context.max_zip_epub_member_bytes,
            )
        except ValueError as exc:
            raise context.resource_limit_error_class(str(exc)) from exc

    if context.copied_epub_bytes + written > context.max_zip_total_epub_bytes:
        extracted_path.unlink(missing_ok=True)
        raise context.resource_limit_error_class(
            "ZIP EPUB contents exceed the "
            f"{format_mib(context.max_zip_total_epub_bytes)} total uncompressed limit."
        )

    context.copied_epub_bytes += written
    return extracted_path


def process_epub_member(*, context: ZipImportContext, member: ZipMember) -> object:
    enforce_member_size_limits(context=context, member=member)
    extracted_path = extract_epub_member(context=context, member=member)

    sidecar_member = zip_sidecar_opf_for_epub(
        epub_member=member.source_name,
        opfs_by_dir=context.index.opfs_by_dir,
        members_index=context.index.members_index,
    )
    sidecar = read_sidecar_opf(
        zf=context.zf,
        member_name=sidecar_member,
        members_index=context.index.members_index,
        max_opf_xml_bytes=context.max_opf_xml_bytes,
    )
    asset_reader = (
        make_sidecar_asset_reader(
            zf=context.zf,
            members_index=context.index.members_index,
            collisions=context.index.collisions,
            max_cover_bytes=context.max_cover_bytes,
        )
        if sidecar is not None
        else None
    )

    import_result = context.import_epub_func(
        str(extracted_path),
        sidecar_opf_bytes=sidecar.data if sidecar is not None else None,
        sidecar_opf_dir=sidecar.directory if sidecar is not None else None,
        sidecar_asset_reader=asset_reader,
    )
    return run_item_from_import_result(
        import_result=import_result,
        source_name=member.safe_source_name,
        import_run_item_factory=context.import_run_item_factory,
        sanitize_error_message=context.sanitize_error_message,
    )


def cleanup_extraction_dir(extraction_dir: Path) -> None:
    if not extraction_dir.exists():
        return
    # Only temp files created in the extraction directory are removed; callers
    # own the original ZIP path and any parent job directory cleanup.
    for child in extraction_dir.iterdir():
        if child.is_file():
            child.unlink(missing_ok=True)
    try:
        extraction_dir.rmdir()
    except OSError:
        pass


def process_zip_import_path(
    *,
    result: ResultT,
    zip_path: Path,
    extraction_dir: Path,
    import_epub_func: Callable[..., object],
    max_opf_xml_bytes: int,
    max_cover_bytes: int,
    import_run_item_factory: Callable[..., object],
    resource_limit_error_class: type[Exception],
    sanitize_error_message: Callable[[object], str],
    log_item_failure: Callable[..., None],
    log_archive_rejected: Callable[..., None],
    max_zip_members: int,
    max_zip_epub_member_bytes: int,
    max_zip_total_epub_bytes: int,
) -> ResultT:
    extraction_dir.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            all_infos = zf.infolist()
            if len(all_infos) > max_zip_members:
                message = f"ZIP contains more than {max_zip_members} entries."
                log_archive_rejected(result=result, safe_message=message)
                raise resource_limit_error_class(message)

            index = build_zip_index(all_infos)
            result.total_found = len(index.epub_members)
            context = ZipImportContext(
                zf=zf,
                index=index,
                extraction_dir=extraction_dir,
                import_epub_func=import_epub_func,
                import_run_item_factory=import_run_item_factory,
                resource_limit_error_class=resource_limit_error_class,
                sanitize_error_message=sanitize_error_message,
                log_item_failure=log_item_failure,
                max_opf_xml_bytes=max_opf_xml_bytes,
                max_cover_bytes=max_cover_bytes,
                max_zip_epub_member_bytes=max_zip_epub_member_bytes,
                max_zip_total_epub_bytes=max_zip_total_epub_bytes,
            )

            for member in index.epub_members:
                try:
                    result.items.append(process_epub_member(context=context, member=member))
                except Exception as exc:
                    safe_message = sanitize_error_message(exc)
                    log_item_failure(
                        result=result,
                        item_source_name=member.safe_source_name,
                        safe_message=safe_message,
                    )
                    result.items.append(
                        failed_run_item(
                            source_name=member.safe_source_name,
                            message=safe_message,
                            import_run_item_factory=import_run_item_factory,
                        )
                    )

        result.finalize_counts()
        return result
    finally:
        cleanup_extraction_dir(extraction_dir)
