from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Iterator
import os
import posixpath
import zipfile

from library.imports.archives import (
    MAX_OPF_SIDECAR_XML_BYTES,
    ZipImportCandidate,
    ZipMember,
    plan_zip_import,
)
from library.imports.cli_sources import (
    ImportSourceAdapter,
    ImportSourceEvent,
    ImportSourceFatalError,
    PreparedImportCandidate,
    failed_source_event,
    relative_label,
    source_sort_key,
)
from library.imports.opf import ParsedSidecarOpf
from library.imports.zip_candidate_metadata import read_archive_cover, read_archive_sidecar


GIB = 1024 * 1024 * 1024
MAX_FOLDER_SOURCE_FILES = 100_000
MAX_FOLDER_SOURCE_BYTES = 500 * GIB


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
                yield failed_source_event(
                    relative_label(path, root),
                    "Could not read import file.",
                    error_category="source_io",
                )
                continue
            source_bytes += size
            if source_bytes > MAX_FOLDER_SOURCE_BYTES:
                raise ImportSourceFatalError("Source files exceed the 500 GiB aggregate limit.")
            label = relative_label(path, root)
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
                    yield failed_source_event(
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
            for name in sorted(directories, key=source_sort_key):
                child = current_path / name
                if child.is_symlink():
                    self.skipped_symlinks += 1
                else:
                    retained.append(name)
            directories[:] = retained
            for name in sorted(filenames, key=source_sort_key):
                path = current_path / name
                if path.is_symlink():
                    self.skipped_symlinks += 1
                    continue
                if path.suffix.casefold() in {".epub", ".zip"}:
                    yield path


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
                yield ImportSourceEvent(source_label=result.source_label, result=result)
            if not plan.candidates:
                return
            file_obj.seek(0)
            with zipfile.ZipFile(file_obj, "r") as archive:
                for candidate in sorted(
                    plan.candidates,
                    key=lambda item: source_sort_key(item.safe_name),
                ):
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
        yield failed_source_event(
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
    return read_archive_sidecar(archive, member, trust_member_size=False)


def _read_archive_candidate_cover(
    archive: zipfile.ZipFile,
    *,
    candidate: ZipImportCandidate,
    sidecar: ParsedSidecarOpf | None,
    members: dict[str, ZipMember],
) -> bytes | None:
    return read_archive_cover(
        archive,
        directory=posixpath.dirname(candidate.safe_name),
        sidecar_name=candidate.sidecar_opf_name,
        sidecar=sidecar,
        members=members,
        adjacent_fallback=False,
    )
