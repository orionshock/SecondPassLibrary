from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import PurePath
from urllib.parse import urlparse
import posixpath
import zipfile

from library.imports.errors import (
    INVALID_ZIP_MESSAGE,
    UNSAFE_ARCHIVE_MEMBER_MESSAGE,
)
from library.imports.results import (
    IMPORT_STATUS_FAILED,
    IMPORT_STATUS_SKIPPED,
    ImportItemResult,
)


MAX_ZIP_MEMBERS = 5000
MAX_ZIP_EPUB_MEMBER_BYTES = 200 * 1024 * 1024
MAX_ZIP_TOTAL_EPUB_BYTES = 2 * 1024 * 1024 * 1024
MAX_OPF_SIDECAR_XML_BYTES = 1024 * 1024


@dataclass(frozen=True)
class ZipMember:
    safe_name: str
    file_size: int
    archive_name: str = ""

    @property
    def source_name(self) -> str:
        return self.safe_name

    @property
    def source_label(self) -> str:
        return safe_import_source_name(self.safe_name)


@dataclass
class ZipIndex:
    members_index: dict[str, ZipMember] = field(default_factory=dict)
    epub_members: list[ZipMember] = field(default_factory=list)
    opfs_by_dir: dict[str, list[str]] = field(default_factory=dict)
    collisions: dict[str, int] = field(default_factory=dict)

    def without_collisions(self) -> ZipIndex:
        if not self.collisions:
            return self

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
            collisions=dict(self.collisions),
        )


@dataclass(frozen=True)
class ZipImportCandidate:
    source_name: str
    safe_name: str
    source_label: str
    file_size: int
    sidecar_opf_name: str | None = None
    archive_name: str = ""
    sidecar_archive_name: str = ""


@dataclass
class ZipImportPlan:
    candidates: list[ZipImportCandidate] = field(default_factory=list)
    item_results: list[ImportItemResult] = field(default_factory=list)
    discovered_count: int = 0
    collisions: dict[str, int] = field(default_factory=dict)


def format_mib(byte_count: int) -> str:
    return f"{byte_count // (1024 * 1024)} MiB"


def safe_import_source_name(source_name: str) -> str:
    return PurePath((source_name or "").replace("\\", "/")).name


def safe_zip_member_name(name: str) -> str | None:
    if not name:
        return None
    if _is_url_like(name):
        return None
    if name.startswith(("/", "\\")) or ":" in name:
        return None

    name = name.replace("\\", "/")
    parts = [part for part in name.split("/") if part != "."]
    if any(part in {"", ".."} for part in parts):
        return None

    normalized = "/".join(parts)
    if not normalized:
        return None
    if normalized.startswith("/") or normalized.startswith("../") or normalized == "..":
        return None
    return normalized


def build_zip_index(infos: list[zipfile.ZipInfo]) -> ZipIndex:
    index = ZipIndex()
    for info in infos:
        if info.is_dir():
            continue
        safe_name = safe_zip_member_name(info.filename)
        if safe_name is None:
            continue
        if safe_name in index.members_index:
            index.collisions[safe_name] = index.collisions.get(safe_name, 1) + 1
            continue

        member = ZipMember(
            safe_name=safe_name,
            file_size=info.file_size,
            archive_name=info.filename,
        )
        index.members_index[safe_name] = member

        lower = safe_name.lower()
        if lower.endswith(".epub"):
            index.epub_members.append(member)
        elif lower.endswith(".opf"):
            index.opfs_by_dir.setdefault(posixpath.dirname(safe_name), []).append(safe_name)

    return index.without_collisions()


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

    metadata_opf = posixpath.join(directory, "metadata.opf") if directory else "metadata.opf"
    if metadata_opf in members_index:
        return metadata_opf

    same_base = posixpath.join(directory, f"{stem}.opf") if directory else f"{stem}.opf"
    if same_base in members_index:
        return same_base

    opfs = opfs_by_dir.get(directory, [])
    if len(opfs) == 1:
        return opfs[0]
    return None


def plan_zip_import(
    zip_file,
    *,
    source_label: str = "archive.zip",
    max_zip_members: int = MAX_ZIP_MEMBERS,
    max_epub_member_bytes: int = MAX_ZIP_EPUB_MEMBER_BYTES,
    max_total_epub_bytes: int = MAX_ZIP_TOTAL_EPUB_BYTES,
) -> ZipImportPlan:
    try:
        with zipfile.ZipFile(zip_file, "r") as archive:
            infos = archive.infolist()
    except Exception:
        return ZipImportPlan(
            item_results=[
                ImportItemResult(
                    status=IMPORT_STATUS_FAILED,
                    source_label=safe_import_source_name(source_label),
                    safe_message=INVALID_ZIP_MESSAGE,
                )
            ]
        )

    if len(infos) > max_zip_members:
        return ZipImportPlan(
            item_results=[
                ImportItemResult(
                    status=IMPORT_STATUS_FAILED,
                    source_label=safe_import_source_name(source_label),
                    safe_message=f"ZIP contains more than {max_zip_members} entries.",
                )
            ]
        )

    index = build_zip_index(infos)
    plan = ZipImportPlan(collisions=dict(index.collisions))
    for collision in sorted(index.collisions):
        plan.item_results.append(
            ImportItemResult(
                status=IMPORT_STATUS_SKIPPED,
                source_label=safe_import_source_name(collision),
                safe_message=UNSAFE_ARCHIVE_MEMBER_MESSAGE,
            )
        )

    total_epub_bytes = 0
    for member in index.epub_members:
        plan.discovered_count += 1
        if member.file_size > max_epub_member_bytes:
            plan.item_results.append(
                ImportItemResult(
                    status=IMPORT_STATUS_FAILED,
                    source_label=member.source_label,
                    safe_message=(
                        "EPUB member exceeds the "
                        f"{format_mib(max_epub_member_bytes)} uncompressed limit."
                    ),
                )
            )
            continue
        if total_epub_bytes + member.file_size > max_total_epub_bytes:
            plan.item_results.append(
                ImportItemResult(
                    status=IMPORT_STATUS_FAILED,
                    source_label=member.source_label,
                    safe_message=(
                        "ZIP EPUB contents exceed the "
                        f"{format_mib(max_total_epub_bytes)} total uncompressed limit."
                    ),
                )
            )
            continue

        # Total payload limit applies to accepted/importable EPUB candidates only.
        # Failed members do not consume this budget.
        total_epub_bytes += member.file_size
        sidecar = zip_sidecar_opf_for_epub(
            epub_member=member.safe_name,
            opfs_by_dir=index.opfs_by_dir,
            members_index=index.members_index,
        )
        plan.candidates.append(
            ZipImportCandidate(
                source_name=member.source_name,
                safe_name=member.safe_name,
                source_label=member.source_label,
                file_size=member.file_size,
                sidecar_opf_name=sidecar,
                archive_name=member.archive_name,
                sidecar_archive_name=(
                    index.members_index[sidecar].archive_name if sidecar else ""
                ),
            )
        )

    return plan


def _is_url_like(value: str) -> bool:
    return urlparse(value).scheme.lower() in {"http", "https", "data"}
