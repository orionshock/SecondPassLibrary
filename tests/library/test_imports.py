from __future__ import annotations

import os
from pathlib import Path
import shutil
from unittest.mock import MagicMock, patch
import uuid

from django.conf import settings
from django.test import TestCase

from library.models import Book, BookFile
from library.services import ImportStatus, import_epub

from tests.library.utils import IsolatedMediaRootMixin


class EPUBImportTest(IsolatedMediaRootMixin, TestCase):
    def setUp(self):
        # Create a temporary EPUB file for testing
        temp_root = Path(settings.BASE_DIR) / "TestFiles"
        temp_root.mkdir(parents=True, exist_ok=True)
        self.temp_dir = str(temp_root / f"tmp_epub_{uuid.uuid4().hex}")
        os.makedirs(self.temp_dir, exist_ok=True)
        self.epub_path = os.path.join(self.temp_dir, "test.epub")
        with open(self.epub_path, "wb") as f:
            f.write(uuid.uuid4().hex.encode("utf-8"))

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch("library.services.epub.read_epub")
    def test_checksum_calculation(self, mock_read_epub):
        mock_book = MagicMock()
        mock_book.get_metadata.return_value = []
        mock_read_epub.return_value = mock_book

        import hashlib

        with open(self.epub_path, "rb") as f:
            expected_checksum = hashlib.sha256(f.read()).hexdigest()

        result = import_epub(self.epub_path)
        self.assertEqual(result.status, ImportStatus.IMPORTED)
        self.assertEqual(result.checksum, expected_checksum)

    def test_invalid_extension(self):
        invalid_path = os.path.join(self.temp_dir, "test.txt")
        with open(invalid_path, "w") as f:
            f.write("not epub")
        with self.assertRaises(ValueError) as cm:
            import_epub(invalid_path)
        self.assertIn("must have .epub extension", str(cm.exception))

    def test_file_not_exists(self):
        non_existent = os.path.join(self.temp_dir, "nonexistent.epub")
        with self.assertRaises(ValueError) as cm:
            import_epub(non_existent)
        self.assertIn("does not exist", str(cm.exception))

    @patch("library.services.epub.read_epub")
    def test_duplicate_detection(self, mock_read_epub):
        # Mock the epub object
        mock_book = MagicMock()
        mock_book.get_metadata.return_value = []
        mock_read_epub.return_value = mock_book

        # Calculate the actual checksum of the temp file
        import hashlib

        with open(self.epub_path, "rb") as f:
            checksum = hashlib.sha256(f.read()).hexdigest()

        # Create a BookFile with the same checksum
        book = Book.objects.create(title="Existing Book")
        BookFile.objects.create(
            book=book,
            file="existing.epub",
            checksum=checksum,
            file_size=123,
            source_filename="existing.epub",
        )

        # Try to import again - should return existing
        result = import_epub(self.epub_path)
        self.assertEqual(result.status, ImportStatus.DUPLICATE)
        self.assertEqual(result.checksum, checksum)
        book_file = result.book_file
        assert book_file is not None

        book = result.book
        assert book is not None
        self.assertEqual(book.title, "Existing Book")

