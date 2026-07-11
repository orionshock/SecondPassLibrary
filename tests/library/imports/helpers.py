from __future__ import annotations

from io import BytesIO
import zipfile

from django.contrib.auth import get_user_model

from library.imports.dto import ImportAuthor, ImportMetadata


class ImportPersistenceFixtureMixin:
    def setUp(self):
        super().setUp()
        User = get_user_model()
        self.actor = User.objects.create_user(username="importer", password="pw")


def sample_metadata(**overrides) -> ImportMetadata:
    values = {
        "title": "Sample Book",
        "sort_title": "Sample Book, The",
        "subtitle": "A Subtitle",
        "authors": [ImportAuthor(name="Sample Author", sort_name="Author, Sample", position=0)],
        "series": None,
        "language": "en",
        "publisher": "Example Press",
        "description": "Example description",
        "published_year": None,
        "published_month": None,
        "published_day": None,
        "published_date_precision": "",
        "tags": [],
        "identifiers": [],
    }
    values.update(overrides)
    return ImportMetadata(**values)


def minimal_epub_bytes(*, metadata_xml: str | None = None, opf_path: str = "OEBPS/content.opf") -> bytes:
    metadata_xml = metadata_xml or """
    <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
      <dc:title>Sample EPUB</dc:title>
      <dc:creator>Sample Author</dc:creator>
      <dc:language>en</dc:language>
    </metadata>
    """
    opf_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf"
         xmlns:opf="http://www.idpf.org/2007/opf"
         unique-identifier="BookId"
         version="3.0">
  {metadata_xml}
  <manifest>
    <item id="chapter" href="chapter.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine>
    <itemref idref="chapter"/>
  </spine>
</package>
"""
    container_xml = f"""<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="{opf_path}" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""
    chapter_path = opf_path.rsplit("/", 1)[0] + "/chapter.xhtml" if "/" in opf_path else "chapter.xhtml"
    out = BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("mimetype", "application/epub+zip")
        zf.writestr("META-INF/container.xml", container_xml)
        zf.writestr(opf_path, opf_xml)
        zf.writestr(
            chapter_path,
            "<html xmlns='http://www.w3.org/1999/xhtml'><body>Chapter</body></html>",
        )
    return out.getvalue()


def zip_bytes(*entries: tuple[str, bytes]) -> BytesIO:
    out = BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries:
            archive.writestr(name, data)
    out.seek(0)
    return out


def metadata_xml(title: str) -> str:
    return f"""
    <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
      <dc:title>{title}</dc:title>
      <dc:creator>Sample Author</dc:creator>
      <dc:language>en</dc:language>
    </metadata>
    """


def sidecar_opf_xml(title: str, *, identifier: str = "") -> str:
    return f"""
    <package xmlns="http://www.idpf.org/2007/opf"
             xmlns:opf="http://www.idpf.org/2007/opf">
      <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
        <dc:title>{title}</dc:title>
        <dc:creator>Sidecar Author</dc:creator>
        <dc:language>en</dc:language>
        {identifier}
      </metadata>
    </package>
    """
