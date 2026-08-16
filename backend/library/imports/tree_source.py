from __future__ import annotations

from pathlib import Path
from typing import Iterator
import os

from library.imports.archives import MAX_OPF_SIDECAR_XML_BYTES, safe_zip_member_name
from library.imports.cli_sources import (
    COVER_NAMES,
    ImportSourceAdapter,
    ImportSourceEvent,
    ImportSourceFatalError,
    PreparedImportCandidate,
    failed_source_event,
    relative_label,
    source_sort_key,
)
from library.imports.covers import MAX_COVER_IMAGE_BYTES
from library.imports.opf import ParsedSidecarOpf, parse_sidecar_opf
from library.imports.results import IMPORT_STATUS_FAILED, IMPORT_STATUS_SKIPPED, ImportItemResult


GIB = 1024 * 1024 * 1024
MAX_TREE_CANDIDATES = 100_000
MAX_TREE_TOTAL_EPUB_BYTES = 500 * GIB


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
            for name in sorted(directories, key=source_sort_key):
                child = current_path / name
                if child.is_symlink():
                    self.skipped_symlinks += 1
                else:
                    retained.append(name)
            directories[:] = retained

            files = []
            for name in sorted(filenames, key=source_sort_key):
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
            label = relative_label(current_path, root) or "tree root"
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
                yield failed_source_event(
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
                        source_label=relative_label(epub_path, root),
                        candidate=PreparedImportCandidate(
                            source_method=self.method,
                            source_label=relative_label(epub_path, root),
                            epub_filename=epub_path.name,
                            file_obj=fp,
                            file_size=size,
                            metadata_label=relative_label(opfs[0], root) if opfs else "",
                            sidecar_opf=sidecar,
                            sidecar_cover_bytes=cover,
                        ),
                    )
            except OSError:
                yield failed_source_event(
                    label,
                    "Could not read EPUB file.",
                    error_category="source_io",
                )


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
    candidates.extend(directory / name for name in COVER_NAMES)
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


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=True).relative_to(root)
        return True
    except (OSError, ValueError):
        return False
