"""
Import orchestration facade for the library app.

Historically, import + metadata helpers lived directly in this module. It now
keeps stable orchestration entry points while delegating focused implementation
details to:

- library/import_services.py (synchronous upload staging and ZIP orchestration)
- library/epub_services.py (EPUB import + metadata extraction)
- library/opf_services.py (OPF sidecar parsing/merge helpers)
- library/cover_services.py (cover validation/storage + embedded cover discovery)
"""

from __future__ import annotations

from ebooklib import epub  # NOTE: tests patch library.services.epub.read_epub

from .cover_services import MAX_COVER_BYTES
from .epub_services import ImportResult
from .epub_services import import_epub_impl as _import_epub_impl
from .import_services import create_import_result_from_upload as _create_import_result_from_upload
from .opf_services import MAX_OPF_SIDECAR_XML_BYTES


def import_epub(
    file_path: str,
    *,
    sidecar_opf_bytes: bytes | None = None,
    sidecar_opf_dir: str | None = None,
    sidecar_asset_reader=None,
) -> ImportResult:
    return _import_epub_impl(
        epub_module=epub,
        file_path=file_path,
        sidecar_opf_bytes=sidecar_opf_bytes,
        sidecar_opf_dir=sidecar_opf_dir,
        sidecar_asset_reader=sidecar_asset_reader,
    )


def create_import_result_from_upload(*, user, uploaded_file):
    # Keep tests' read_epub patch working by using the public import_epub()
    # wrapper as the injected importer.
    return _create_import_result_from_upload(
        user=user,
        uploaded_file=uploaded_file,
        import_epub_func=import_epub,
        max_opf_xml_bytes=MAX_OPF_SIDECAR_XML_BYTES,
        max_cover_bytes=MAX_COVER_BYTES,
    )
