from __future__ import annotations

import hashlib
from io import BytesIO
import os
from pathlib import Path
import shutil
from unittest.mock import MagicMock, patch
import uuid

from django.conf import settings
from django.test import TestCase

from library.imports.epub import calculate_file_sha256, ImportStatus
from library.imports.epub import import_epub
from tests.utils.books import create_file_backed_book

from tests.library.utils import IsolatedMediaRootMixin


class NoUnboundedReadBytesIO(BytesIO):
    def __init__(self, initial_bytes: bytes):
        super().__init__(initial_bytes)
        self.read_sizes: list[int] = []

    def read(self, size: int = -1) -> bytes:
        self.read_sizes.append(size)
        if size < 0:
            raise AssertionError("checksum helper must not call unbounded read()")
        return super().read(size)


class ChunkedUpload:
    def __init__(self, data: bytes):
        self.data = data
        self.seek_positions: list[int] = []
        self.chunks_called = False

    def seek(self, position: int) -> None:
        self.seek_positions.append(position)

    def chunks(self, *, chunk_size: int | None = None):
        self.chunks_called = True
        size = chunk_size or len(self.data)
        for start in range(0, len(self.data), size):
            yield self.data[start : start + size]

    def read(self, size: int = -1) -> bytes:
        raise AssertionError("checksum helper should use UploadedFile.chunks() when available")


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

    def test_stream_sha256_uses_bounded_reads_for_regular_file_and_rewinds(self):
        data = b"abcdef"
        file_obj = NoUnboundedReadBytesIO(data)

        checksum, file_size = calculate_file_sha256(file_obj, chunk_size=2)

        self.assertEqual(checksum, hashlib.sha256(data).hexdigest())
        self.assertEqual(file_size, len(data))
        self.assertEqual(file_obj.tell(), 0)
        self.assertTrue(file_obj.read_sizes)
        self.assertTrue(all(size == 2 for size in file_obj.read_sizes))

    def test_stream_sha256_uses_uploaded_file_chunks_and_rewinds(self):
        data = b"abcdef"
        upload = ChunkedUpload(data)

        checksum, file_size = calculate_file_sha256(upload, chunk_size=2)

        self.assertEqual(checksum, hashlib.sha256(data).hexdigest())
        self.assertEqual(file_size, len(data))
        self.assertTrue(upload.chunks_called)
        self.assertEqual(upload.seek_positions, [0, 0])

    @patch("library.imports.epub.epub.read_epub")
    def test_checksum_calculation(self, mock_read_epub):
        mock_book = MagicMock()
        mock_book.get_metadata.return_value = []
        mock_read_epub.return_value = mock_book

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

    @patch("library.imports.epub.epub.read_epub")
    def test_duplicate_detection(self, mock_read_epub):
        # Mock the epub object
        mock_book = MagicMock()
        mock_book.get_metadata.return_value = []
        mock_read_epub.return_value = mock_book

        # Calculate the actual checksum of the temp file
        with open(self.epub_path, "rb") as f:
            checksum = hashlib.sha256(f.read()).hexdigest()

        # Create a BookFile with the same checksum
        with open(self.epub_path, "rb") as f:
            epub_bytes = f.read()
        create_file_backed_book(
            title="Existing Book",
            epub_bytes=epub_bytes,
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
