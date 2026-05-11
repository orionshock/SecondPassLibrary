from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from library.group_services import ensure_book_public_assignment
from library.models import Book, BookFile
from reading.w3c import build_fragment_selector, build_publication_source, build_target, normalize_epub_cfi
from tests.reading.utils import IsolatedUserdataMixin


User = get_user_model()


class W3CHelpersTest(IsolatedUserdataMixin, TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u", password="p")
        self.book = Book.objects.create(title="B")
        ensure_book_public_assignment(book=self.book, added_by=None)

    def test_normalize_epub_cfi_wraps_raw_paths(self):
        self.assertEqual(normalize_epub_cfi("/6/4"), "epubcfi(/6/4)")
        self.assertEqual(normalize_epub_cfi(" epubcfi(/6/4) "), "epubcfi(/6/4)")

    def test_build_fragment_selector_requires_cfi(self):
        with self.assertRaises(ValueError):
            build_fragment_selector("")

    def test_build_publication_source_prefers_checksum_identity(self):
        dummy = SimpleUploadedFile("dummy.epub", b"epub")
        BookFile.objects.create(book=self.book, file=dummy, checksum="a" * 64)
        source = build_publication_source(book=self.book)
        self.assertEqual(source["id"], f"book:sha256:{'a' * 64}")
        self.assertEqual(source["fileHash"], f"sha256:{'a' * 64}")

    def test_build_target_includes_source_selector_and_locator(self):
        target = build_target(book=self.book, current_location={"cfi": "/6/2", "href": "Text/c1.xhtml"})
        self.assertIn("source", target)
        self.assertIn("selector", target)
        self.assertEqual(target["selector"]["value"], "epubcfi(/6/2)")
        self.assertEqual(target["locator"]["href"], "Text/c1.xhtml")
