from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import BinaryIO, Iterator
import os
import posixpath
import zipfile

from library.imports.archives import (
    MAX_OPF_SIDECAR_XML_BYTES,
    ZipImportCandidate,
    ZipMember,
    build_zip_index,
    plan_zip_import,
    resolve_zip_member_reference,
    safe_zip_member_name,
    zip_sidecar_opf_for_epub,
)
from library.imports.covers import MAX_COVER_IMAGE_BYTES
from library.imports.opf import ParsedSidecarOpf, parse_sidecar_opf
from library.imports.results import (
    IMPORT_STATUS_FAILED,
    IMPORT_STATUS_SKIPPED,
    ImportItemResult,
)


GIB = 1024 * 1024 * 1024
MAX_FOLDER_SOURCE_FILES = 100_000
MAX_FOLDER_SOURCE_BYTES = 500 * GIB
MAX_AIO_ZIP_COMPRESSED_BYTES = 20 * GIB
MAX_AIO_ZIP_MEMBERS = 250_000
MAX_AIO_ZIP_CANDIDATES = 100_000
MAX_AIO_ZIP_TOTAL_EPUB_BYTES = 500 * GIB
MAX_TREE_CANDIDATES = 100_000
MAX_TREE_TOTAL_EPUB_BYTES = 500 * GIB
MAX_OUTER_MEMBER_COMPRESSION_RATIO = 100
_COVER_NAMES = ("cover.jpg", "cover.jpeg", "cover.png", "cover.webp")


class ImportSourceFatalError(Exception):
    pass


@dataclass(frozen=True)
class PreparedImportCandidate:
    source_method: str
    source_label: str
    epub_filename: str
    file_obj: BinaryIO
    file_size: int
    metadata_label: str = ""
    sidecar_opf: ParsedSidecarOpf | None = None
    sidecar_cover_bytes: bytes | None = None


@dataclass(frozen=True)
class ImportSourceEvent:
    source_label: str
    candidate: PreparedImportCandidate | None = None
    result: ImportItemResult | None = None
    ambiguous: bool = False

    @property
    def processed_bytes(self) -> int:
        return self.candidate.file_size if self.candidate is not None else 0


class ImportSourceAdapter:
    method = "unknown"
    limit_description = ""

    def __init__(self, source: Path):
        self.source = source
        self.skipped_symlinks = 0
        self.skipped_members = 0

    @property
    def source_label(self) -> str:
        return self.source.name or str(self.source)

    def iter_events(self) -> Iterator[ImportSourceEvent]:
        raise NotImplementedError


class FolderOfArchivesSource(ImportSourceAdapter):
    method = "folder_of_zip"
    limit_description = (
        "100,000 EPUB/ZIP source files; 500 GiB source bytes; existing per-ZIP limits"
    )

    def iter_events(self) -> Iterator[ImportSourceEvent]:
        paths, root = self._source_paths()
        source_count = 0
        source_bytes = 0
        for path in paths:
            source_count += 1
            if source_count > MAX_FOLDER_SOURCE_FILES:
                raise ImportSourceFatalError(
                    f"Source contains more than {MAX_FOLDER_SOURCE_FILES:,} EPUB/ZIP files."
                )
            try:
                size = path.stat().st_size
            except OSError:
                yield _failed_source_event(
                    _relative_label(path, root),
                    "Could not read import file.",
                    error_category="source_io",
                )
                continue
            source_bytes += size
            if source_bytes > MAX_FOLDER_SOURCE_BYTES:
                raise ImportSourceFatalError("Source files exceed the 500 GiB aggregate limit.")
            label = _relative_label(path, root)
            if path.suffix.casefold() == ".epub":
                try:
                    with path.open("rb") as fp:
                        yield ImportSourceEvent(
                            source_label=label,
                            candidate=PreparedImportCandidate(
                                source_method=self.method,
                                source_label=label,
                                epub_filename=path.name,
                                file_obj=fp,
                                file_size=size,
                            ),
                        )
                except OSError:
                    yield _failed_source_event(
                        label,
                        "Could not read import file.",
                        error_category="source_io",
                    )
                continue
            yield from _iter_generic_zip_events(
                path=path,
                source_label=label,
                source_method=self.method,
            )

    def _source_paths(self) -> tuple[Iterator[Path], Path]:
        if not self.source.exists():
            raise ImportSourceFatalError("Import path does not exist.")
        if self.source.is_file():
            if self.source.suffix.casefold() not in {".epub", ".zip"}:
                raise ImportSourceFatalError("Source file must be an EPUB or ZIP.")
            return iter((self.source,)), self.source.parent
        if not self.source.is_dir():
            raise ImportSourceFatalError("Import path is not a file or directory.")
        root = self.source.resolve()
        return self._walk_source_files(root), root

    def _walk_source_files(self, root: Path) -> Iterator[Path]:
        for current, directories, filenames in os.walk(root, followlinks=False):
            current_path = Path(current)
            retained = []
            for name in sorted(directories, key=_sort_key):
                child = current_path / name
                if child.is_symlink():
                    self.skipped_symlinks += 1
                else:
                    retained.append(name)
            directories[:] = retained
            for name in sorted(filenames, key=_sort_key):
                path = current_path / name
                if path.is_symlink():
                    self.skipped_symlinks += 1
                    continue
                if path.suffix.casefold() in {".epub", ".zip"}:
                    yield path


class AioZipSource(ImportSourceAdapter):
    method = "aio_zip"
    limit_description = (
        "20 GiB compressed ZIP; 250,000 members; 100,000 candidates; "
        "500 GiB EPUB bytes"
    )

    def iter_events(self) -> Iterator[ImportSourceEvent]:
        if not self.source.is_file() or self.source.suffix.casefold() != ".zip":
            raise ImportSourceFatalError("Source must be one readable ZIP file.")
        try:
            source_size = self.source.stat().st_size
        except OSError as exc:
            raise ImportSourceFatalError("Could not inspect source ZIP.") from exc
        if source_size > MAX_AIO_ZIP_COMPRESSED_BYTES:
            raise ImportSourceFatalError("Source ZIP exceeds the 20 GiB compressed limit.")

        try:
            with zipfile.ZipFile(self.source, "r", allowZip64=True) as archive:
                infos = archive.infolist()
                if len(infos) > MAX_AIO_ZIP_MEMBERS:
                    raise ImportSourceFatalError(
                        f"Source ZIP contains more than {MAX_AIO_ZIP_MEMBERS:,} entries."
                    )
                if any(info.flag_bits & 0x1 for info in infos if not info.is_dir()):
                    raise ImportSourceFatalError("Encrypted ZIP members are not supported.")
                index = build_zip_index(infos)
                if index.unsafe_member_count:
                    raise ImportSourceFatalError("Source ZIP contains unsafe member paths.")
                if index.collisions:
                    raise ImportSourceFatalError(
                        "Source ZIP contains duplicate normalized member paths."
                    )
                yield from self._iter_archive_events(archive, index)
        except ImportSourceFatalError:
            raise
        except (OSError, zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
            raise ImportSourceFatalError("Invalid or unreadable source ZIP.") from exc

    def _iter_archive_events(self, archive: zipfile.ZipFile, index) -> Iterator[ImportSourceEvent]:
        groups: dict[str, dict[str, list[ZipMember]]] = {}
        for member in index.epub_members:
            groups.setdefault(posixpath.dirname(member.safe_name), {"epubs": [], "opfs": []})[
                "epubs"
            ].append(member)
        for directory, opf_names in index.opfs_by_dir.items():
            group = groups.setdefault(directory, {"epubs": [], "opfs": []})
            group["opfs"].extend(index.members_index[name] for name in opf_names)

        if len(groups) > MAX_AIO_ZIP_CANDIDATES:
            raise ImportSourceFatalError(
                f"Source ZIP contains more than {MAX_AIO_ZIP_CANDIDATES:,} logical candidates."
            )

        total_epub_bytes = 0
        for directory in sorted(groups, key=_sort_key):
            group = groups[directory]
            epubs = sorted(group["epubs"], key=lambda item: _sort_key(item.safe_name))
            label = directory or "archive root"
            if not epubs:
                yield ImportSourceEvent(
                    source_label=label,
                    result=ImportItemResult(
                        status=IMPORT_STATUS_SKIPPED,
                        source_label=label,
                        safe_message="Metadata exists without an EPUB.",
                        error_category="missing_epub",
                    ),
                )
                continue
            if len(epubs) > 1:
                yield ImportSourceEvent(
                    source_label=label,
                    result=ImportItemResult(
                        status=IMPORT_STATUS_FAILED,
                        source_label=label,
                        safe_message="Candidate directory contains multiple EPUB files.",
                        error_category="ambiguous_epub",
                    ),
                    ambiguous=True,
                )
                continue

            member = epubs[0]
            if member.file_size > 200 * 1024 * 1024:
                yield _failed_source_event(
                    member.safe_name,
                    "EPUB member exceeds the 200 MiB limit.",
                    error_category="epub_too_large",
                )
                continue
            if _has_extreme_compression(member):
                yield _failed_source_event(
                    member.safe_name,
                    "EPUB member exceeds the outer ZIP compression-ratio limit.",
                    error_category="compression_ratio",
                )
                continue
            total_epub_bytes += member.file_size
            if total_epub_bytes > MAX_AIO_ZIP_TOTAL_EPUB_BYTES:
                raise ImportSourceFatalError("Source ZIP EPUB contents exceed 500 GiB.")

            sidecar_name = zip_sidecar_opf_for_epub(
                epub_member=member.safe_name,
                opfs_by_dir=index.opfs_by_dir,
                members_index=index.members_index,
            )
            sidecar = _read_archive_sidecar(archive, index.members_index.get(sidecar_name or ""))
            cover = _read_archive_cover(
                archive,
                directory=directory,
                sidecar_name=sidecar_name,
                sidecar=sidecar,
                members=index.members_index,
            )
            try:
                with archive.open(member.archive_name or member.safe_name, "r") as fp:
                    yield ImportSourceEvent(
                        source_label=member.safe_name,
                        candidate=PreparedImportCandidate(
                            source_method=self.method,
                            source_label=member.safe_name,
                            epub_filename=posixpath.basename(member.safe_name),
                            file_obj=fp,
                            file_size=member.file_size,
                            metadata_label=sidecar_name or "",
                            sidecar_opf=sidecar,
                            sidecar_cover_bytes=cover,
                        ),
                    )
            except (OSError, RuntimeError, zipfile.BadZipFile):
                yield _failed_source_event(
                    member.safe_name,
                    "Could not read EPUB member.",
                    error_category="source_io",
                )


class TreeSource(ImportSourceAdapter):
    method = "tree"
    limit_description = "100,000 candidates; 500 GiB EPUB bytes; no followed symlinks"

    def iter_events(self) -> Iterator[ImportSourceEvent]:
        if not self.source.is_dir():
            raise ImportSourceFatalError("Source must be a readable directory tree.")
        root = self.source.resolve()
        candidate_count = 0
        total_epub_bytes = 0
        for current, directories, filenames in os.walk(root, followlinks=False):
            current_path = Path(current)
            retained = []
            for name in sorted(directories, key=_sort_key):
                child = current_path / name
                if child.is_symlink():
                    self.skipped_symlinks += 1
                else:
                    retained.append(name)
            directories[:] = retained

            files = []
            for name in sorted(filenames, key=_sort_key):
                path = current_path / name
                if path.is_symlink():
                    self.skipped_symlinks += 1
                else:
                    files.append(path)
            epubs = [path for path in files if path.suffix.casefold() == ".epub"]
            opfs = [path for path in files if path.name.casefold() == "metadata.opf"]
            if not epubs and not opfs:
                continue

            candidate_count += 1
            if candidate_count > MAX_TREE_CANDIDATES:
                raise ImportSourceFatalError(
                    f"Source tree contains more than {MAX_TREE_CANDIDATES:,} candidates."
                )
            label = _relative_label(current_path, root) or "tree root"
            if not epubs:
                yield ImportSourceEvent(
                    source_label=label,
                    result=ImportItemResult(
                        status=IMPORT_STATUS_SKIPPED,
                        source_label=label,
                        safe_message="Metadata exists without an EPUB.",
                        error_category="missing_epub",
                    ),
                )
                continue
            if len(epubs) > 1:
                yield ImportSourceEvent(
                    source_label=label,
                    result=ImportItemResult(
                        status=IMPORT_STATUS_FAILED,
                        source_label=label,
                        safe_message="Candidate directory contains multiple EPUB files.",
                        error_category="ambiguous_epub",
                    ),
                    ambiguous=True,
                )
                continue
            if len(opfs) > 1:
                yield ImportSourceEvent(
                    source_label=label,
                    result=ImportItemResult(
                        status=IMPORT_STATUS_FAILED,
                        source_label=label,
                        safe_message="Candidate directory contains ambiguous metadata.opf files.",
                        error_category="ambiguous_opf",
                    ),
                    ambiguous=True,
                )
                continue

            epub_path = epubs[0]
            if not _is_within(epub_path, root):
                raise ImportSourceFatalError("Candidate path escaped the source root.")
            try:
                size = epub_path.stat().st_size
            except OSError:
                yield _failed_source_event(
                    label,
                    "Could not inspect EPUB file.",
                    error_category="source_io",
                )
                continue
            total_epub_bytes += size
            if total_epub_bytes > MAX_TREE_TOTAL_EPUB_BYTES:
                raise ImportSourceFatalError("Source tree EPUB contents exceed 500 GiB.")
            sidecar = _read_tree_sidecar(opfs[0] if opfs else None)
            cover = _read_tree_cover(current_path, sidecar=sidecar, root=root)
            try:
                with epub_path.open("rb") as fp:
                    yield ImportSourceEvent(
                        source_label=_relative_label(epub_path, root),
                        candidate=PreparedImportCandidate(
                            source_method=self.method,
                            source_label=_relative_label(epub_path, root),
                            epub_filename=epub_path.name,
                            file_obj=fp,
                            file_size=size,
                            metadata_label=(
                                _relative_label(opfs[0], root) if opfs else ""
                            ),
                            sidecar_opf=sidecar,
                            sidecar_cover_bytes=cover,
                        ),
                    )
            except OSError:
                yield _failed_source_event(
                    label,
                    "Could not read EPUB file.",
                    error_category="source_io",
                )


def _iter_generic_zip_events(
    *, path: Path, source_label: str, source_method: str
) -> Iterator[ImportSourceEvent]:
    try:
        with path.open("rb") as file_obj:
            plan = plan_zip_import(file_obj, source_label=source_label)
            for result in plan.item_results:
                result = replace(
                    result,
                    source_label=f"{source_label}!{result.source_label}",
                )
                yield ImportSourceEvent(
                    source_label=result.source_label,
                    result=result,
                )
            if not plan.candidates:
                return
            file_obj.seek(0)
            with zipfile.ZipFile(file_obj, "r") as archive:
                for candidate in sorted(plan.candidates, key=lambda item: _sort_key(item.safe_name)):
                    candidate_label = f"{source_label}!{candidate.safe_name}"
                    sidecar = _read_archive_sidecar_candidate(archive, candidate)
                    cover = _read_archive_candidate_cover(
                        archive,
                        candidate=candidate,
                        sidecar=sidecar,
                        members=plan.members_index,
                    )
                    with archive.open(candidate.archive_name or candidate.safe_name, "r") as fp:
                        yield ImportSourceEvent(
                            source_label=candidate_label,
                            candidate=PreparedImportCandidate(
                                source_method=source_method,
                                source_label=candidate_label,
                                epub_filename=candidate.source_name,
                                file_obj=fp,
                                file_size=candidate.file_size,
                                metadata_label=candidate.sidecar_opf_name or "",
                                sidecar_opf=sidecar,
                                sidecar_cover_bytes=cover,
                            ),
                        )
    except (OSError, zipfile.BadZipFile, RuntimeError):
        yield _failed_source_event(
            source_label,
            "Could not read import ZIP.",
            error_category="source_io",
        )


def _read_archive_sidecar_candidate(
    archive: zipfile.ZipFile, candidate: ZipImportCandidate
) -> ParsedSidecarOpf | None:
    if not candidate.sidecar_opf_name:
        return None
    member = ZipMember(
        safe_name=candidate.sidecar_opf_name,
        archive_name=candidate.sidecar_archive_name,
        file_size=MAX_OPF_SIDECAR_XML_BYTES,
    )
    return _read_archive_sidecar(archive, member, trust_member_size=False)


def _read_archive_sidecar(
    archive: zipfile.ZipFile,
    member: ZipMember | None,
    *,
    trust_member_size: bool = True,
) -> ParsedSidecarOpf | None:
    if member is None or (trust_member_size and member.file_size > MAX_OPF_SIDECAR_XML_BYTES):
        return None
    try:
        with archive.open(member.archive_name or member.safe_name, "r") as fp:
            data = fp.read(MAX_OPF_SIDECAR_XML_BYTES + 1)
        if len(data) > MAX_OPF_SIDECAR_XML_BYTES:
            return None
        return parse_sidecar_opf(data)
    except Exception:
        return None


def _read_archive_candidate_cover(
    archive: zipfile.ZipFile,
    *,
    candidate: ZipImportCandidate,
    sidecar: ParsedSidecarOpf | None,
    members: dict[str, ZipMember],
) -> bytes | None:
    return _read_archive_cover(
        archive,
        directory=posixpath.dirname(candidate.safe_name),
        sidecar_name=candidate.sidecar_opf_name,
        sidecar=sidecar,
        members=members,
        adjacent_fallback=False,
    )


def _read_archive_cover(
    archive: zipfile.ZipFile,
    *,
    directory: str,
    sidecar_name: str | None,
    sidecar: ParsedSidecarOpf | None,
    members: dict[str, ZipMember],
    adjacent_fallback: bool = True,
) -> bytes | None:
    member = None
    if sidecar is not None and sidecar.cover_href and sidecar_name:
        member = resolve_zip_member_reference(
            base_member=sidecar_name,
            href=sidecar.cover_href,
            members_index=members,
        )
    if member is None and adjacent_fallback:
        for name in _COVER_NAMES:
            candidate_name = posixpath.join(directory, name) if directory else name
            if candidate_name in members:
                member = members[candidate_name]
                break
    if member is None or member.file_size > MAX_COVER_IMAGE_BYTES:
        return None
    try:
        with archive.open(member.archive_name or member.safe_name, "r") as fp:
            data = fp.read(MAX_COVER_IMAGE_BYTES + 1)
        return data if len(data) == member.file_size and len(data) <= MAX_COVER_IMAGE_BYTES else None
    except Exception:
        return None


def _read_tree_sidecar(path: Path | None) -> ParsedSidecarOpf | None:
    if path is None:
        return None
    try:
        if path.stat().st_size > MAX_OPF_SIDECAR_XML_BYTES:
            return None
        with path.open("rb") as fp:
            data = fp.read(MAX_OPF_SIDECAR_XML_BYTES + 1)
        return parse_sidecar_opf(data) if len(data) <= MAX_OPF_SIDECAR_XML_BYTES else None
    except Exception:
        return None


def _read_tree_cover(
    directory: Path, *, sidecar: ParsedSidecarOpf | None, root: Path
) -> bytes | None:
    candidates = []
    if sidecar is not None and sidecar.cover_href:
        safe_href = safe_zip_member_name(sidecar.cover_href)
        if safe_href:
            candidates.append(directory / Path(*safe_href.split("/")))
    candidates.extend(directory / name for name in _COVER_NAMES)
    seen = set()
    for path in candidates:
        normalized = str(path).casefold()
        if normalized in seen:
            continue
        seen.add(normalized)
        try:
            if path.is_symlink() or not path.is_file() or not _is_within(path, root):
                continue
            if path.stat().st_size > MAX_COVER_IMAGE_BYTES:
                continue
            with path.open("rb") as fp:
                data = fp.read(MAX_COVER_IMAGE_BYTES + 1)
            if len(data) <= MAX_COVER_IMAGE_BYTES:
                return data
        except OSError:
            continue
    return None


def _has_extreme_compression(member: ZipMember) -> bool:
    return bool(
        member.file_size
        and (
            member.compress_size == 0
            or member.file_size > member.compress_size * MAX_OUTER_MEMBER_COMPRESSION_RATIO
        )
    )


def _failed_source_event(
    source_label: str, message: str, *, error_category: str
) -> ImportSourceEvent:
    return ImportSourceEvent(
        source_label=source_label,
        result=ImportItemResult(
            status=IMPORT_STATUS_FAILED,
            source_label=source_label,
            safe_message=message,
            error_category=error_category,
        ),
    )


def _relative_label(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.name


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=True).relative_to(root)
        return True
    except (OSError, ValueError):
        return False


def _sort_key(value: str) -> tuple[str, str]:
    return value.casefold(), value
