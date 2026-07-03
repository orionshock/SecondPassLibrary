from django.contrib.auth import get_user_model
from django.test import TestCase

from library.group_services import ensure_book_public_assignment
from library.models import BookFile
from reading.profile import normalize_epub_cfi
from reading.w3c import build_publication_source
from tests.reading.utils import IsolatedUserdataMixin
from tests.utils.books import create_file_backed_book


User = get_user_model()


class W3CHelpersTest(IsolatedUserdataMixin, TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u", password="p")
        self.book = create_file_backed_book(title="B", assign_public=False).book
        ensure_book_public_assignment(book=self.book, added_by=None)

    def test_normalize_epub_cfi_wraps_raw_paths(self):
        self.assertEqual(normalize_epub_cfi("/6/4"), "epubcfi(/6/4)")
        self.assertEqual(normalize_epub_cfi(" epubcfi(/6/4) "), "epubcfi(/6/4)")

    def test_build_publication_source_prefers_checksum_identity(self):
        # Override the checksum to keep this test stable and focused.
        book_file = BookFile.objects.get(book=self.book)
        book_file.checksum = "a" * 64
        book_file.save(update_fields=["checksum", "updated_at"])
        self.book.refresh_from_db()
        source = build_publication_source(book=self.book)
        self.assertEqual(source["id"], f"book:sha256:{'a' * 64}")
        self.assertEqual(source["fileHash"], f"sha256:{'a' * 64}")
