from __future__ import annotations

from library.imports.errors import InvalidEpubImportError
from library.imports.epub_package import open_epub_package
from library.imports.opf import ParsedSidecarOpf, parse_opf_metadata


def read_import_metadata(data: bytes, *, sidecar_opf: ParsedSidecarOpf | None = None):
    try:
        with open_epub_package(data) as package:
            epub_metadata = parse_opf_metadata(package.read_package_document())
    except InvalidEpubImportError:
        raise
    except Exception as exc:
        raise InvalidEpubImportError() from exc
    if sidecar_opf is None:
        return epub_metadata
    return _read_sidecar_metadata_or_fallback(
        sidecar_metadata=sidecar_opf.metadata,
        fallback_metadata=epub_metadata,
    )


def _read_sidecar_metadata_or_fallback(*, sidecar_metadata, fallback_metadata):
    if not _sidecar_has_real_title(sidecar_metadata):
        return fallback_metadata
    return sidecar_metadata


def _sidecar_has_real_title(metadata) -> bool:
    title = metadata.title.strip()
    return bool(title) and title.casefold() != "untitled"
