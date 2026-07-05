from __future__ import annotations

import io
from unittest.mock import MagicMock
import zipfile

from django.contrib.auth.models import User
from rest_framework.test import APITestCase

from accounts.models import UserProfile
from library.groups.services import ensure_user_public_membership
from tests.testenv.filesystem import IsolatedImportsMixin


def mock_epub() -> MagicMock:
    mock_book = MagicMock()
    mock_book.get_metadata.side_effect = lambda ns, name: {
        "title": [("Test Title", {})],
        "creator": [("Test Author", {})],
        "language": [("en", {})],
    }.get(name, [])
    return mock_book


def png_bytes(*, size: tuple[int, int] = (32, 48)) -> bytes:
    from PIL import Image

    img = Image.new("RGB", size, color=(4, 5, 6))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def epub_with_embedded_cover_bytes(*, cover_size: tuple[int, int] = (10, 12)) -> bytes:
    """
    Minimal EPUB zip bytes that embedded cover extraction can read.
    """
    cover_bytes = png_bytes(size=cover_size)
    container_xml = """<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""
    opf_xml = """<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="BookId" version="3.0">
  <manifest>
    <item id="c1" href="images/cover.png" media-type="image/png" properties="cover-image"/>
  </manifest>
</package>
"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("mimetype", "application/epub+zip")
        zf.writestr("META-INF/container.xml", container_xml)
        zf.writestr("OEBPS/content.opf", opf_xml)
        zf.writestr("OEBPS/images/cover.png", cover_bytes)
    return buf.getvalue()


class BaseImportApiTest(IsolatedImportsMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(username="u1", password="pw")
        self.other = User.objects.create_user(username="u2", password="pw")
        ensure_user_public_membership(user=self.user)
        ensure_user_public_membership(user=self.other)

    def set_user_role(self, *, role: str) -> None:
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.role = role
        profile.save(update_fields=["role", "updated_at"])

    def _login_librarian(self) -> None:
        self.set_user_role(role=UserProfile.ROLE_LIBRARIAN)
        self.client.login(username="u1", password="pw")
