from __future__ import annotations

from typing import Iterator
import posixpath
import zipfile

from library.imports.archives import ZipMember, build_zip_index, zip_sidecar_opf_for_epub
from library.imports.cli_sources import (
    ImportSourceAdapter,
    ImportSourceEvent,
    ImportSourceFatalError,
    PreparedImportCandidate,
    failed_source_event,
    source_sort_key,
)
from library.imports.results import IMPORT_STATUS_FAILED, IMPORT_STATUS_SKIPPED, ImportItemResult
from library.imports.zip_candidate_metadata import read_archive_cover, read_archive_sidecar


GIB = 1024 * 1024 * 1024
MAX_AIO_ZIP_COMPRESSED_BYTES = 20 * GIB
MAX_AIO_ZIP_MEMBERS = 250_000
MAX_AIO_ZIP_CANDIDATES = 100_000
MAX_AIO_ZIP_TOTAL_EPUB_BYTES = 500 * GIB
MAX_OUTER_MEMBER_COMPRESSION_RATIO = 100


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
        for directory in sorted(groups, key=source_sort_key):
            group = groups[directory]
            epubs = sorted(group["epubs"], key=lambda item: source_sort_key(item.safe_name))
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
                yield failed_source_event(
                    member.safe_name,
                    "EPUB member exceeds the 200 MiB limit.",
                    error_category="epub_too_large",
                )
                continue
            if _has_extreme_compression(member):
                yield failed_source_event(
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
            sidecar = read_archive_sidecar(archive, index.members_index.get(sidecar_name or ""))
            cover = read_archive_cover(
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
                yield failed_source_event(
                    member.safe_name,
                    "Could not read EPUB member.",
                    error_category="source_io",
                )


def _has_extreme_compression(member: ZipMember) -> bool:
    return bool(
        member.file_size
        and (
            member.compress_size == 0
            or member.file_size > member.compress_size * MAX_OUTER_MEMBER_COMPRESSION_RATIO
        )
    )
