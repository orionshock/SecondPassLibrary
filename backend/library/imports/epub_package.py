from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from io import BytesIO
from pathlib import PurePosixPath
import posixpath
from urllib.parse import urlparse
import zipfile

from defusedxml import ElementTree

from library.imports.errors import InvalidEpubImportError


MAX_CONTAINER_XML_BYTES = 128 * 1024
MAX_PACKAGE_OPF_BYTES = 1024 * 1024
CONTAINER_MEMBER = "META-INF/container.xml"
PACKAGE_MEDIA_TYPE = "application/oebps-package+xml"
_URL_SCHEMES = {"http", "https", "data"}


class EpubPackage:
    """Provide bounded, safe access to one discovered EPUB package."""

    def __init__(
        self,
        archive: zipfile.ZipFile,
        package_path: str,
        package_document: bytes,
    ) -> None:
        self._archive = archive
        self._package_path = package_path
        self._package_document = package_document

    @property
    def package_path(self) -> str:
        return self._package_path

    def read_package_document(self) -> bytes:
        return self._package_document

    def resolve_package_reference(self, href: str) -> str | None:
        safe_href = _safe_member_path(href)
        if safe_href is None:
            return None
        package_dir = posixpath.dirname(self.package_path)
        candidate = posixpath.normpath(posixpath.join(package_dir, safe_href))
        return _safe_member_path(candidate)

    def read_member(self, member: str, *, max_bytes: int) -> bytes:
        safe_member = _safe_member_path(member)
        if safe_member is None or safe_member != member:
            raise InvalidEpubImportError()
        return _read_bounded_member(self._archive, safe_member, max_bytes=max_bytes)


@contextmanager
def open_epub_package(data: bytes) -> Iterator[EpubPackage]:
    try:
        with zipfile.ZipFile(BytesIO(data), "r") as archive:
            container_xml = _read_bounded_member(
                archive,
                CONTAINER_MEMBER,
                max_bytes=MAX_CONTAINER_XML_BYTES,
            )
            package_path = _find_package_path(container_xml)
            # Discovery includes existence and size validation of the required OPF.
            package_document = _read_bounded_member(
                archive,
                package_path,
                max_bytes=MAX_PACKAGE_OPF_BYTES,
            )
            package = EpubPackage(archive, package_path, package_document)
            yield package
    except InvalidEpubImportError:
        raise
    except Exception as exc:
        raise InvalidEpubImportError() from exc


def _read_bounded_member(
    archive: zipfile.ZipFile,
    member: str,
    *,
    max_bytes: int,
) -> bytes:
    try:
        info = archive.getinfo(member)
    except KeyError as exc:
        raise InvalidEpubImportError() from exc
    if info.file_size > max_bytes:
        raise InvalidEpubImportError()
    with archive.open(info, "r") as source:
        data = source.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise InvalidEpubImportError()
    return data


def _find_package_path(container_xml: bytes) -> str:
    try:
        root = ElementTree.fromstring(container_xml)
    except Exception as exc:
        raise InvalidEpubImportError() from exc

    for item in root.iter():
        if _local_name(item.tag) != "rootfile":
            continue
        media_type = (item.attrib.get("media-type") or "").strip()
        full_path = (item.attrib.get("full-path") or "").strip()
        if media_type and media_type != PACKAGE_MEDIA_TYPE:
            continue
        safe_path = _safe_member_path(full_path)
        if safe_path:
            return safe_path
    raise InvalidEpubImportError()


def _safe_member_path(path: str) -> str | None:
    value = (path or "").strip().replace("\\", "/")
    if not value or value.startswith("/") or ":" in value or "\x00" in value:
        return None
    if urlparse(value).scheme.lower() in _URL_SCHEMES:
        return None
    pure = PurePosixPath(value)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        return None
    normalized = str(pure)
    if normalized.startswith("../") or normalized == ".." or normalized.startswith("/"):
        return None
    return normalized


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]
