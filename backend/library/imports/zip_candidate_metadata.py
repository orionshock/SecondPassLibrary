from __future__ import annotations

import posixpath
import zipfile

from library.imports.archives import (
    MAX_OPF_SIDECAR_XML_BYTES,
    ZipMember,
    resolve_zip_member_reference,
)
from library.imports.cli_sources import COVER_NAMES
from library.imports.covers import MAX_COVER_IMAGE_BYTES
from library.imports.opf import ParsedSidecarOpf, parse_sidecar_opf


def read_archive_sidecar(
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


def read_archive_cover(
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
        for name in COVER_NAMES:
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
