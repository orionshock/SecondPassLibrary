from __future__ import annotations

from pathlib import Path, PurePath
import posixpath
import uuid
import zipfile
from typing import BinaryIO, Callable


MAX_ZIP_UPLOAD_BYTES = 1024 * 1024 * 1024
MAX_ZIP_MEMBERS = 5000
MAX_ZIP_EPUB_MEMBER_BYTES = 200 * 1024 * 1024
MAX_ZIP_TOTAL_EPUB_BYTES = 2 * 1024 * 1024 * 1024
COPY_CHUNK_BYTES = 1024 * 1024


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

    # Normalize harmless "./" segments so directory matching (e.g. metadata.opf)
    # remains stable across ZIP tools.
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
    members_index: dict[str, zipfile.ZipInfo],
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


def process_zip_import_path(
    *,
    result,
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
):
    extraction_dir.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            all_infos = zf.infolist()
            if len(all_infos) > max_zip_members:
                message = f"ZIP contains more than {max_zip_members} entries."
                log_archive_rejected(result=result, safe_message=message)
                raise resource_limit_error_class(message)

            members_index: dict[str, zipfile.ZipInfo] = {}
            epub_members: list[zipfile.ZipInfo] = []
            opfs_by_dir: dict[str, list[str]] = {}
            collisions: set[str] = set()

            for info in all_infos:
                if info.is_dir():
                    continue
                safe_name = safe_zip_member_name(info.filename)
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
                    directory = posixpath.dirname(safe_name)
                    opfs_by_dir.setdefault(directory, []).append(safe_name)

            if collisions:
                members_index = {
                    key: value
                    for (key, value) in members_index.items()
                    if key not in collisions
                }
                epub_members = [info for info in epub_members if info.filename not in collisions]
                for directory, names in list(opfs_by_dir.items()):
                    filtered = [name for name in names if name not in collisions]
                    if filtered:
                        opfs_by_dir[directory] = filtered
                    else:
                        opfs_by_dir.pop(directory, None)

            result.total_found = len(epub_members)

            copied_epub_bytes = 0
            for info in epub_members:
                source_name = info.filename
                safe_source_name = safe_import_source_name(source_name)
                try:
                    if info.file_size > max_zip_epub_member_bytes:
                        raise resource_limit_error_class(
                            "EPUB member exceeds the "
                            f"{format_mib(max_zip_epub_member_bytes)} uncompressed limit."
                        )
                    if copied_epub_bytes + info.file_size > max_zip_total_epub_bytes:
                        raise resource_limit_error_class(
                            "ZIP EPUB contents exceed the "
                            f"{format_mib(max_zip_total_epub_bytes)} total uncompressed limit."
                        )

                    extracted_path = extraction_dir / f"{uuid.uuid4().hex}.epub"
                    with zf.open(info, "r") as src:
                        try:
                            written = copy_fileobj_capped(
                                src=src,
                                dst_path=extracted_path,
                                max_bytes=max_zip_epub_member_bytes,
                            )
                        except ValueError as exc:
                            raise resource_limit_error_class(str(exc)) from exc
                    if copied_epub_bytes + written > max_zip_total_epub_bytes:
                        extracted_path.unlink(missing_ok=True)
                        raise resource_limit_error_class(
                            "ZIP EPUB contents exceed the "
                            f"{format_mib(max_zip_total_epub_bytes)} total uncompressed limit."
                        )
                    copied_epub_bytes += written

                    sidecar_opf_member = zip_sidecar_opf_for_epub(
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
                            if sidecar_opf_bytes and len(sidecar_opf_bytes) > max_opf_xml_bytes:
                                sidecar_opf_bytes = None
                            else:
                                sidecar_opf_dir = posixpath.dirname(sidecar_opf_member)
                        except Exception:
                            sidecar_opf_bytes = None
                            sidecar_opf_dir = None

                    def asset_reader(member: str) -> bytes | None:
                        safe = safe_zip_member_name(member)
                        if safe is None or safe in collisions or safe not in members_index:
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
                            asset_reader if sidecar_opf_bytes and sidecar_opf_dir else None
                        ),
                    )

                    status_val = getattr(import_result, "status", None)
                    item_status = (
                        "imported"
                        if status_val == "imported"
                        else "duplicate"
                        if status_val == "duplicate"
                        else "failed"
                    )
                    result.items.append(
                        import_run_item_factory(
                            status=item_status,
                            source_name=safe_source_name,
                            book=getattr(import_result, "book", None),
                            book_file=getattr(import_result, "book_file", None),
                            message=(
                                str(getattr(import_result, "message", "") or "")
                                if item_status in {"imported", "duplicate"}
                                else sanitize_error_message(
                                    getattr(import_result, "message", "") or ""
                                )
                            ),
                        )
                    )
                except Exception as exc:
                    safe_message = sanitize_error_message(exc)
                    log_item_failure(
                        result=result,
                        item_source_name=safe_source_name,
                        safe_message=safe_message,
                    )
                    result.items.append(
                        import_run_item_factory(
                            status="failed",
                            source_name=safe_source_name,
                            message=safe_message,
                        )
                    )
                    continue

        result.finalize_counts()
        return result
    finally:
        if extraction_dir.exists():
            for child in extraction_dir.iterdir():
                if child.is_file():
                    child.unlink(missing_ok=True)
            try:
                extraction_dir.rmdir()
            except OSError:
                pass
